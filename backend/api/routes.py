import asyncio
import json

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import sys
import os

from config import config
from database import db
from services.ollama_client import ollama_client
from services.chat_reader import ChatReader
from services.entity_extractor import EntityExtractor
from services.lorebook_updater import LorebookUpdater
from services.hallucination_detector import HallucinationDetector
from services.backup_manager import BackupManager
from services.lorebook_builder import LorebookBuilder
from utils.file_ops import FileOperations
from utils.scan_lock import scan_lock_manager

router = APIRouter()

# Map plural entity type keys (used internally) to singular DB values
ENTITY_TYPE_MAP = {
    'npcs': 'npc',
    'factions': 'faction',
    'locations': 'location',
    'items': 'item',
    'aliases': 'alias',
    'stats': 'stat',
    'mythology': 'mythology',
}

# Pydantic models for request/response
class ConfigUpdate(BaseModel):
    key: str
    value: str

class ScanRequest(BaseModel):
    chat_file: str
    force_rescan: Optional[bool] = False  # Set true to ignore checkpoint

class EntityApproval(BaseModel):
    action: str  # 'approve' or 'reject'

class EntityEdit(BaseModel):
    entity_data: Dict

class ChatMapping(BaseModel):
    chat_file: str
    character_file: str
    persona_file: Optional[str] = None

class LorebookBuildRequest(BaseModel):
    mode: str  # 'freeform' or 'structured'
    text: Optional[str] = None  # For freeform mode
    categories: Optional[Dict[str, str]] = None  # For structured mode
    target: str  # Path to target lorebook file
    lorebook_name: Optional[str] = None

class LorebookCreateRequest(BaseModel):
    name: str

class VerifyPathRequest(BaseModel):
    path: str
    type: str  # 'chats', 'characters', 'lorebooks', 'personas'

# Config endpoints
@router.get("/config")
async def get_config():
    """Get all configuration settings"""
    return {
        "ollama": {
            "url": config.ollama_url,
            "reader_model": config.get('ollama.reader_model', config.ollama_model),
            "coder_model": config.get('ollama.coder_model', config.ollama_model),
            "model": config.ollama_model,
            "has_api_key": config.ollama_api_key is not None
        },
        "sillytavern": {
            "chats_dir": config.chats_dir,
            "characters_dir": config.characters_dir,
            "personas_dir": config.personas_dir,
            "lorebooks_dir": config.lorebooks_dir
        },
        "scanning": config.get('scanning', {}),
        "auto_apply": config.get('auto_apply', {}),
        "entity_tracking": config.get('entity_tracking', {})
    }

@router.post("/config")
async def update_config(updates: Dict):
    """Update configuration settings (deep-merges nested dicts)"""
    try:
        def deep_merge(target: dict, source: dict):
            """Recursively merge source into target, preserving existing keys."""
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    deep_merge(target[key], value)
                else:
                    target[key] = value

        deep_merge(config.data, updates)
        config.save()
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Test endpoints
@router.post("/test/ollama")
async def test_ollama():
    """Test Ollama connection"""
    success, message = await ollama_client.test_connection()
    
    # Always try to get model list so frontend can populate dropdowns
    models = await ollama_client.list_models()
    
    if success:
        return {
            "status": "success",
            "message": message,
            "available_models": models
        }
    else:
        return {
            "status": "error",
            "message": message,
            "available_models": models  # Still include models even on partial failure
        }

# Scan endpoints
@router.post("/scan/manual")
async def manual_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Manually trigger a scan of a chat file with chunking"""
    try:
        # Get chat mapping
        mapping = await db.get_chat_mapping(request.chat_file)
        if not mapping:
            # Try to guess from config
            character_file = config.chat_mappings.get(request.chat_file)
            if not character_file:
                raise HTTPException(
                    status_code=400,
                    detail=f"No character mapping found for {request.chat_file}. Please configure in settings."
                )
        else:
            character_file = mapping["character_file"]
        
        # Run scan in background with chunking
        background_tasks.add_task(
            run_scan,
            request.chat_file,
            character_file,
            request.force_rescan
        )
        
        return {
            "status": "started",
            "message": f"Scan started for {request.chat_file} (chunked processing)",
            "force_rescan": request.force_rescan
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_scan(chat_file: str, character_file: str, force_rescan: bool = False):
    """Background task to run a scan with chunking"""
    # Acquire scan lock to prevent concurrent scans on the same file
    if not await scan_lock_manager.acquire_scan_lock(chat_file):
        print(f"Scan already in progress for {chat_file}, skipping.")
        return
    
    try:
        # Helper to broadcast progress via WebSocket
        async def broadcast_progress(data: dict):
            try:
                from main import app
                if hasattr(app.state, 'broadcast'):
                    await app.state.broadcast(data)
            except Exception:
                pass  # WebSocket broadcast is best-effort
        
        # Initialize services
        reader = ChatReader(config.chats_dir)
        from services.chunk_processor import ChunkProcessor
        chunk_processor = ChunkProcessor(reader)
        extractor = EntityExtractor(ollama_client)
        hallucination_detector = HallucinationDetector()
        
        # Rate limiting config
        rate_limit_delay = config.get('ollama.rate_limit_delay', 2)
        batch_size = config.get('ollama.batch_size', 5)
        
        # Get chunks to process (with checkpoint tracking)
        chunks, metadata = await chunk_processor.get_chunks_to_process(
            chat_file,
            force_rescan=force_rescan
        )
        
        if not chunks:
            await db.add_scan_record(
                chat_file, character_file, 0, 0, 'completed',
                "No new messages to scan (checkpoint up to date)"
            )
            return
        
        # Broadcast scan started
        await broadcast_progress({
            "type": "scan_progress",
            "chat_file": chat_file,
            "status": "started",
            "total_chunks": len(chunks),
            "current_chunk": 0,
            "entities_found": 0
        })
        
        # Process each chunk one at a time (generator pattern — fixes memory leak)
        all_entities = {
            'npcs': [],
            'factions': [],
            'locations': [],
            'items': [],
            'aliases': [],
            'stats': []
        }
        
        total_entities = 0
        
        for chunk_idx, chunk_texts in enumerate(chunks):
            try:
                # Extract entities from this chunk
                chunk_entities = await extractor.extract_entities(chunk_texts)
                
                # Run hallucination detection on this chunk
                source_text = "\n".join(chunk_texts)
                chunk_entities = hallucination_detector.filter_hallucinations(
                    chunk_entities, source_text
                )
                
                # Merge with existing entities (avoid duplicates)
                for entity_type, entity_list in chunk_entities.items():
                    for entity in entity_list:
                        existing = next(
                            (e for e in all_entities.get(entity_type, []) 
                             if e.get('name', '').lower() == entity.get('name', '').lower()),
                            None
                        )
                        
                        if existing:
                            if entity.get('confidence', 0) > existing.get('confidence', 0):
                                existing.update(entity)
                        else:
                            all_entities[entity_type].append(entity)
                
                # Explicit cleanup of chunk data
                del chunk_entities
                del source_text
                
            except Exception as e:
                print(f"Error processing chunk {chunk_idx + 1}: {e}")
                continue
            
            # Update running entity count and broadcast progress
            total_entities = sum(len(v) for v in all_entities.values())
            await broadcast_progress({
                "type": "scan_progress",
                "chat_file": chat_file,
                "status": "processing",
                "total_chunks": len(chunks),
                "current_chunk": chunk_idx + 1,
                "entities_found": total_entities
            })
            
            # Rate limiting: pause every batch_size chunks
            if (chunk_idx + 1) % batch_size == 0 and chunk_idx + 1 < len(chunks):
                await asyncio.sleep(rate_limit_delay)
        
        # Count total entities found
        total_entities = sum(len(all_entities.get(t, [])) for t in all_entities.keys())
        
        # Add entities to queue (using singular type names for DB)
        char_path = f"{config.characters_dir}/{character_file}"
        source_context = f"Messages {metadata['start_index']}-{metadata['end_index']} from {chat_file}"
        
        for entity_type, entity_list in all_entities.items():
            db_type = ENTITY_TYPE_MAP.get(entity_type, entity_type)
            for entity in entity_list:
                await db.add_entity(
                    entity_type=db_type,
                    entity_name=entity.get('name', 'Unknown'),
                    entity_data=entity,
                    target_file=char_path,
                    source_messages=source_context,
                    confidence_score=entity.get('confidence', 0.5)
                )
        
        # Update checkpoint
        await chunk_processor.update_checkpoint(
            chat_file,
            metadata['end_index'],
            metadata['total_messages']
        )
        
        # Record scan
        await db.add_scan_record(
            chat_file, character_file,
            metadata['end_index'] - metadata['start_index'],
            total_entities,
            'completed'
        )
        
        # Broadcast completion
        await broadcast_progress({
            "type": "scan_complete",
            "chat_file": chat_file,
            "entities_found": total_entities
        })
        
    except Exception as e:
        await db.add_scan_record(
            chat_file, character_file, 0, 0, 'failed', str(e)
        )
    finally:
        # Always release the scan lock
        await scan_lock_manager.release_scan_lock(chat_file)

# Queue endpoints
@router.get("/queue")
async def get_queue(entity_type: Optional[str] = None):
    """Get all pending entities awaiting review"""
    entities = await db.get_pending_entities(entity_type)
    return {"entities": entities, "count": len(entities)}

@router.post("/queue/{entity_id}/approve")
async def approve_entity(entity_id: int):
    """Approve an entity and apply it to the lorebook"""
    try:
        # Get entity directly by ID
        entity = await db.fetch_one(
            "SELECT * FROM entity_queue WHERE id = ? AND status = 'pending'",
            (entity_id,)
        )
        
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        # Parse JSON data
        import json
        entity['entity_data'] = json.loads(entity['entity_data'])
        
        # Apply to lorebook (standalone vs character-embedded)
        updater = LorebookUpdater()
        if updater.is_standalone_lorebook(entity['target_file']):
            success = await updater.add_entry_standalone(
                lorebook_file=entity['target_file'],
                entity=entity['entity_data'],
                entity_type=entity['entity_type']
            )
        else:
            success = await updater.add_entry(
                character_file=entity['target_file'],
                entity=entity['entity_data'],
                entity_type=entity['entity_type']
            )
        
        if success:
            # Update status
            await db.update_entity_status(entity_id, 'approved')
            
            # Record in history
            await db.add_update_record(
                entity_id=entity_id,
                entity_type=entity['entity_type'],
                entity_name=entity['entity_name'],
                target_file=entity['target_file'],
                action='added',
                new_value=entity['entity_data']
            )
            
            return {"status": "success", "message": "Entity approved and added"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add entity")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/{entity_id}/reject")
async def reject_entity(entity_id: int):
    """Reject an entity"""
    await db.update_entity_status(entity_id, 'rejected')
    return {"status": "success", "message": "Entity rejected"}

@router.put("/queue/{entity_id}")
async def edit_entity(entity_id: int, edit: EntityEdit):
    """Edit an entity before approval"""
    await db.update_entity_data(entity_id, edit.entity_data)
    return {"status": "success", "message": "Entity updated"}

# History endpoints
@router.get("/history/scans")
async def get_scan_history(limit: int = 50):
    """Get scan history"""
    history = await db.get_scan_history(limit)
    return {"scans": history, "count": len(history)}

@router.get("/history/updates")
async def get_update_history(limit: int = 100):
    """Get applied updates history"""
    history = await db.get_update_history(limit)
    return {"updates": history, "count": len(history)}

# File management endpoints
@router.get("/files/chats")
async def list_chats():
    """List available chat files"""
    reader = ChatReader(config.chats_dir)
    chat_files = reader.list_chat_files()
    
    # Get info for each chat
    chats_info = []
    for chat_file in chat_files:
        try:
            info = reader.get_chat_info(chat_file)
            chats_info.append(info)
        except:
            continue
    
    return {"chats": chats_info, "count": len(chats_info)}

@router.get("/files/characters")
async def list_characters():
    """List available character files (recursive)"""
    try:
        path_str = config.characters_dir
        if not path_str or not os.path.exists(path_str):
            return {"characters": [], "count": 0}
            
        path_obj = Path(path_str)
        files = []
        
        # Search for .json, .png, .webp
        for ext in ["*.json", "*.png", "*.webp"]:
            files.extend([str(f.relative_to(path_obj)) for f in path_obj.rglob(ext)])
            
        # Deduplicate and sort
        files = sorted(list(set(files)))
        
        return {"characters": files, "count": len(files)}
    except Exception as e:
        print(f"Error listing characters: {e}")
        return {"characters": [], "count": 0}

@router.get("/files/personas")
async def list_personas():
    """List available persona files (recursive)"""
    try:
        path_str = config.personas_dir
        if not path_str or not os.path.exists(path_str):
            return {"personas": [], "count": 0}
            
        path_obj = Path(path_str)
        files = []
        
        # Search for .json, .png, .webp
        for ext in ["*.json", "*.png", "*.webp"]:
            files.extend([str(f.relative_to(path_obj)) for f in path_obj.rglob(ext)])
            
        # Deduplicate and sort
        files = sorted(list(set(files)))
        
        return {"personas": files, "count": len(files)}
    except Exception as e:
        print(f"Error listing personas: {e}")
        return {"personas": [], "count": 0}

@router.get("/files/backups")
async def list_backups(file_path: Optional[str] = None):
    """List available backups"""
    backups = await db.get_backups(file_path)
    return {"backups": backups, "count": len(backups)}

@router.post("/files/verify-path")
async def verify_path(request: VerifyPathRequest):
    """Verify a directory path and list found files recursively"""
    try:
        path_obj = Path(request.path)
        
        # Diagnostics
        server_info = f"[Server: {sys.platform}, CWD: {os.getcwd()}]"
        
        # basic checks
        if not path_obj.exists():
            return {"status": "error", "message": f"❌ Path not found {server_info}"}
        if not path_obj.is_dir():
            return {"status": "error", "message": f"❌ Not a directory {server_info}"}
            
        # Permission check & file scan
        files = []
        pattern = "*.json"  # Default
        
        if request.type == 'chats':
            pattern = "*.jsonl"
        elif request.type == 'characters':
             # SillyTavern characters can be JSON or PNG/WEBP cards
            files = [str(f.relative_to(path_obj)) for f in path_obj.rglob("*.json")]
            files.extend([str(f.relative_to(path_obj)) for f in path_obj.rglob("*.png")])
            files.extend([str(f.relative_to(path_obj)) for f in path_obj.rglob("*.webp")])
            
            count = len(files)
            if count == 0:
                 return {
                    "status": "warning", 
                    "message": f"⚠ Directory exists but no characters (.json/.png/.webp) found",
                    "count": 0,
                    "files": []
                }
            
            return {
                "status": "success",
                "message": f"✓ Valid! Found {count} files",
                "count": count,
                "files": files[:5]
            }
            
        elif request.type == 'personas':
            # Personas can also be JSON or PNG/WEBP
            files = [str(f.relative_to(path_obj)) for f in path_obj.rglob("*.json")]
            files.extend([str(f.relative_to(path_obj)) for f in path_obj.rglob("*.png")])
            files.extend([str(f.relative_to(path_obj)) for f in path_obj.rglob("*.webp")])
            
            count = len(files)
            if count == 0:
                 return {
                    "status": "warning", 
                    "message": f"⚠ Directory exists but no personas (.json/.png/.webp) found",
                    "count": 0,
                    "files": []
                }
            
            return {
                "status": "success",
                "message": f"✓ Valid! Found {count} files",
                "count": count,
                "files": files[:5]
            }

        # Recursive scan with limit
        count = 0
        sample_files = []
        
        try:
            # Use distinct loop to avoid building massive list in memory if folder is huge
            for f in path_obj.rglob(pattern):
                count += 1
                if count <= 5:
                    sample_files.append(str(f.relative_to(path_obj)))
                
                # Safety cap for very large folders
                if count >= 10000:
                    break
                    
            if count == 0:
                return {
                    "status": "warning", 
                    "message": f"⚠ Directory exists but no {pattern} files found",
                    "count": 0,
                    "files": []
                }
                
            return {
                "status": "success",
                "message": f"✓ Valid! Found {count}+ files",
                "count": count,
                "files": sample_files
            }
            
        except PermissionError:
             return {"status": "error", "message": "❌ Permission denied accessing this directory"}
             
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}

@router.post("/files/restore/{backup_id}")
async def restore_backup(backup_id: int):
    """Restore from a backup"""
    try:
        # Look up the backup record
        backups = await db.get_backups()
        backup_record = next(
            (b for b in backups if b['id'] == backup_id),
            None
        )
        
        if not backup_record:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        backup_mgr = BackupManager()
        success = await backup_mgr.restore_backup(
            backup_path=backup_record['backup_path'],
            target_path=backup_record['file_path']
        )
        
        if success:
            return {"status": "success", "message": f"Restored {backup_record['file_path']} from backup"}
        else:
            raise HTTPException(status_code=500, detail="Restore failed")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chat mapping endpoints
@router.get("/mappings")
async def get_chat_mappings():
    """Get all chat to character mappings"""
    mappings = await db.get_all_chat_mappings()
    
    # Also include config mappings
    config_mappings = config.chat_mappings
    
    return {
        "database_mappings": mappings,
        "config_mappings": config_mappings
    }

@router.post("/mappings")
async def add_chat_mapping(mapping: ChatMapping):
    """Add or update a chat to character mapping"""
    await db.add_chat_mapping(
        mapping.chat_file,
        mapping.character_file,
        mapping.persona_file
    )
    return {"status": "success", "message": "Mapping saved"}

# Statistics endpoint
@router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    # Get pending count
    pending = await db.get_pending_entities()
    
    # Get last scan
    scans = await db.get_scan_history(1)
    last_scan = scans[0] if scans else None
    
    # Get today's update count via SQL
    today_count_row = await db.fetch_one(
        "SELECT COUNT(*) as cnt FROM update_history WHERE date(applied_at) = date('now')"
    )
    today_updates_count = today_count_row['cnt'] if today_count_row else 0
    
    return {
        "pending_count": len(pending),
        "applied_today": today_updates_count,
        "last_scan": last_scan,
        "total_scans": len(await db.get_scan_history(1000))
    }

# ──────────────────────────────────────────────
#  Lorebook Builder endpoints
# ──────────────────────────────────────────────

@router.post("/lorebook/build")
async def build_lorebook(request: LorebookBuildRequest, background_tasks: BackgroundTasks):
    """Submit freeform or structured text for lorebook processing"""
    try:
        builder = LorebookBuilder(ollama_client)
        
        if request.mode == 'freeform':
            if not request.text or not request.text.strip():
                raise HTTPException(status_code=400, detail="Text is required for freeform mode")
            
            background_tasks.add_task(
                _run_lorebook_build,
                builder, 'freeform', request.text, None,
                request.target, request.lorebook_name
            )
        elif request.mode == 'structured':
            if not request.categories:
                raise HTTPException(status_code=400, detail="Categories are required for structured mode")
            
            # Check at least one category has content
            has_content = any(v and v.strip() for v in request.categories.values())
            if not has_content:
                raise HTTPException(status_code=400, detail="At least one category must have content")
            
            background_tasks.add_task(
                _run_lorebook_build,
                builder, 'structured', None, request.categories,
                request.target, request.lorebook_name
            )
        else:
            raise HTTPException(status_code=400, detail="Mode must be 'freeform' or 'structured'")
        
        return {
            "status": "started",
            "message": f"Lorebook build started in {request.mode} mode"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_lorebook_build(
    builder: LorebookBuilder,
    mode: str,
    text: str,
    categories: Dict,
    target: str,
    lorebook_name: str
):
    """Background task to run lorebook building"""
    try:
        # Broadcast start via WebSocket
        try:
            from main import app
            if hasattr(app.state, 'broadcast'):
                await app.state.broadcast({
                    "type": "lorebook_build_progress",
                    "status": "started",
                    "mode": mode
                })
        except Exception:
            pass
        
        if mode == 'freeform':
            result = await builder.process_freeform(text, target, lorebook_name)
        else:
            result = await builder.process_structured(categories, target, lorebook_name)
        
        # Broadcast completion
        try:
            from main import app
            if hasattr(app.state, 'broadcast'):
                await app.state.broadcast({
                    "type": "lorebook_build_complete",
                    "status": result.get('status', 'unknown'),
                    "entities_found": result.get('entities_found', 0),
                    "lorebook_entries": result.get('lorebook_entries', 0)
                })
        except Exception:
            pass
        
        print(f"✓ Lorebook build complete: {result}")
    except Exception as e:
        print(f"✗ Lorebook build failed: {e}")
        try:
            from main import app
            if hasattr(app.state, 'broadcast'):
                await app.state.broadcast({
                    "type": "lorebook_build_error",
                    "error": str(e)
                })
        except Exception:
            pass


@router.get("/lorebook/list")
async def list_lorebooks():
    """List all available lorebooks"""
    try:
        builder = LorebookBuilder(ollama_client)
        lorebooks = await builder.list_lorebooks()
        return {"lorebooks": lorebooks, "count": len(lorebooks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
#  Character Forge endpoints
# ──────────────────────────────────────────────

from services.character_builder import CharacterBuilder

class CharacterCreateRequest(BaseModel):
    description: str

class CharacterModifyRequest(BaseModel):
    character_data: Dict[str, Any]
    instructions: str

class CharacterSaveRequest(BaseModel):
    filename: str
    character_data: Dict[str, Any]

@router.post("/character/create")
async def create_character_profile(request: CharacterCreateRequest):
    """Generate a new character profile from description"""
    try:
        builder = CharacterBuilder(ollama_client)
        result = await builder.generate_character(request.description)
        return {"status": "success", "character": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/character/modify")
async def modify_character_profile(request: CharacterModifyRequest):
    """Modify an existing character profile"""
    try:
        builder = CharacterBuilder(ollama_client)
        result = await builder.modify_character(request.character_data, request.instructions)
        return {"status": "success", "character": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/character/summary")
async def summarize_character_profile(request: CharacterModifyRequest):
    """Summarize a character for context (uses modify request model for data)"""
    try:
        builder = CharacterBuilder(ollama_client)
        summary = await builder.summarize_character(request.character_data)
        return {"status": "success", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/character/save")
async def save_character_file(request: CharacterSaveRequest):
    """Save character data to a JSON file"""
    try:
        # Ensure filename ends with .json
        filename = request.filename
        if not filename.endswith('.json'):
            filename += '.json'
            
        # Sanitize filename (basic)
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
        
        path = Path(config.characters_dir) / filename
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(request.character_data, f, indent=4)
            
        return {"status": "success", "message": f"Character saved to {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/character/load")
async def load_character(filename: str):
    """Load character data from a JSON or PNG/WebP character card"""
    try:
        path = Path(config.characters_dir) / filename
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="Character file not found")
        
        suffix = path.suffix.lower()
        
        if suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        
        elif suffix == '.png':
            # SillyTavern PNG cards: character JSON is base64-encoded in a tEXt chunk with keyword "chara"
            import base64
            import struct
            
            with open(path, 'rb') as f:
                # Skip PNG signature (8 bytes)
                f.read(8)
                
                while True:
                    # Read chunk: length (4 bytes) + type (4 bytes)
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break
                    
                    length = struct.unpack('>I', chunk_header[:4])[0]
                    chunk_type = chunk_header[4:8].decode('ascii', errors='ignore')
                    chunk_data = f.read(length)
                    f.read(4)  # Skip CRC
                    
                    if chunk_type == 'tEXt':
                        # tEXt chunk: keyword\0value
                        null_idx = chunk_data.index(b'\x00')
                        keyword = chunk_data[:null_idx].decode('ascii')
                        value = chunk_data[null_idx + 1:]
                        
                        if keyword == 'chara':
                            decoded = base64.b64decode(value).decode('utf-8')
                            return json.loads(decoded)
                    
                    elif chunk_type == 'IEND':
                        break
            
            raise HTTPException(status_code=422, detail="PNG file does not contain character card data (no 'chara' tEXt chunk)")
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {suffix}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lorebook/create")
async def create_lorebook(request: LorebookCreateRequest):
    """Create a new empty standalone lorebook"""
    try:
        updater = LorebookUpdater()
        result = await updater.create_standalone_lorebook(request.name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lorebook/{name}")
async def get_lorebook(name: str):
    """Get lorebook contents by name"""
    try:
        builder = LorebookBuilder(ollama_client)
        
        # Search for the lorebook by name across all known locations
        lorebooks = await builder.list_lorebooks()
        match = next(
            (lb for lb in lorebooks if lb['name'] == name or Path(lb['file']).stem == name),
            None
        )
        
        if not match:
            raise HTTPException(status_code=404, detail=f"Lorebook '{name}' not found")
        
        result = await builder.get_lorebook(match['file'])
        if not result:
            raise HTTPException(status_code=404, detail="Could not read lorebook")
        
        result['file'] = match['file']
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
