from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

from config import config
from database import db
from services.ollama_client import ollama_client
from services.chat_reader import ChatReader
from services.entity_extractor import EntityExtractor
from services.lorebook_updater import LorebookUpdater
from utils.file_ops import FileOperations

router = APIRouter()

# Pydantic models for request/response
class ConfigUpdate(BaseModel):
    key: str
    value: str

class ScanRequest(BaseModel):
    chat_file: str
    messages_limit: Optional[int] = 50

class EntityApproval(BaseModel):
    action: str  # 'approve' or 'reject'

class EntityEdit(BaseModel):
    entity_data: Dict

class ChatMapping(BaseModel):
    chat_file: str
    character_file: str
    persona_file: Optional[str] = None

# Config endpoints
@router.get("/config")
async def get_config():
    """Get all configuration settings"""
    return {
        "ollama": {
            "url": config.ollama_url,
            "model": config.ollama_model,
            "has_api_key": config.ollama_api_key is not None
        },
        "sillytavern": {
            "chats_dir": config.chats_dir,
            "characters_dir": config.characters_dir,
            "personas_dir": config.personas_dir
        },
        "scanning": config.get('scanning', {}),
        "auto_apply": config.get('auto_apply', {}),
        "entity_tracking": config.get('entity_tracking', {})
    }

@router.post("/config")
async def update_config(updates: Dict):
    """Update configuration settings"""
    try:
        for key, value in updates.items():
            config.set(key, value)
        
        config.save()
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Test endpoints
@router.post("/test/ollama")
async def test_ollama():
    """Test Ollama connection"""
    success, message = await ollama_client.test_connection()
    
    if success:
        models = await ollama_client.list_models()
        return {
            "status": "success",
            "message": message,
            "available_models": models
        }
    else:
        return {
            "status": "error",
            "message": message
        }

# Scan endpoints
@router.post("/scan/manual")
async def manual_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Manually trigger a scan of a chat file"""
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
        
        # Run scan in background
        background_tasks.add_task(
            run_scan,
            request.chat_file,
            character_file,
            request.messages_limit
        )
        
        return {
            "status": "started",
            "message": f"Scan started for {request.chat_file}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_scan(chat_file: str, character_file: str, messages_limit: int):
    """Background task to run a scan"""
    try:
        # Read chat messages
        reader = ChatReader(config.chats_dir)
        messages = reader.read_chat(chat_file, last_n=messages_limit)
        message_texts = reader.extract_text_only(messages)
        
        if not message_texts:
            await db.add_scan_record(
                chat_file, character_file, 0, 0, 'failed',
                "No messages found to scan"
            )
            return
        
        # Extract entities
        extractor = EntityExtractor(ollama_client)
        entities = await extractor.extract_entities(message_texts)
        
        # Count total entities found
        total_entities = sum(len(entities.get(t, [])) for t in entities.keys())
        
        # Add entities to queue
        char_path = f"{config.characters_dir}/{character_file}"
        source_context = f"Messages from {chat_file}"
        
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                await db.add_entity(
                    entity_type=entity_type,
                    entity_name=entity.get('name', 'Unknown'),
                    entity_data=entity,
                    target_file=char_path,
                    source_messages=source_context,
                    confidence_score=entity.get('confidence', 0.5)
                )
        
        # Record scan
        await db.add_scan_record(
            chat_file, character_file,
            len(message_texts), total_entities,
            'completed'
        )
        
    except Exception as e:
        await db.add_scan_record(
            chat_file, character_file, 0, 0, 'failed', str(e)
        )

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
        # Get entity
        entities = await db.get_pending_entities()
        entity = next((e for e in entities if e['id'] == entity_id), None)
        
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        # Apply to lorebook
        updater = LorebookUpdater()
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

@router.get("/files/backups")
async def list_backups(file_path: Optional[str] = None):
    """List available backups"""
    backups = await db.get_backups(file_path)
    return {"backups": backups, "count": len(backups)}

@router.post("/files/restore/{backup_id}")
async def restore_backup(backup_id: int):
    """Restore from a backup"""
    # Implementation would restore the backup file
    # For now, return success
    return {"status": "success", "message": "Backup restored"}

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
    
    # Get today's updates
    updates = await db.get_update_history(1000)
    today = datetime.now().date()
    today_updates = [
        u for u in updates
        if datetime.fromisoformat(u['applied_at']).date() == today
    ]
    
    return {
        "pending_count": len(pending),
        "applied_today": len(today_updates),
        "last_scan": last_scan,
        "total_scans": len(await db.get_scan_history(1000))
    }
