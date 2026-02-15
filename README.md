# SillyTavern Campaign Manager (STCM)

**Automated lorebook and persona management for SillyTavern campaigns**

STCM uses Ollama to automatically scan your D&D campaign chat logs and update lorebooks with new NPCs, factions, locations, items, and character aliases - no manual entry required!

---

## Features

✅ **Auto-detect entities** from chat logs using local LLM (Ollama)  
✅ **Review queue** - approve, reject, or edit before applying  
✅ **Multi-campaign support** - link chats to specific lorebooks  
✅ **Automatic backups** before any changes  
✅ **Scheduled scans** - run hourly, daily, or on-demand  
✅ **Web interface** - manage everything from your browser  
✅ **Character aliases** - auto-track disguises and alternate identities  
✅ **Persona updates** - track stats, gold, equipment changes  

---

## Quick Start

### Prerequisites

- Python 3.9+
- Ollama installed and running ([ollama.ai](https://ollama.ai))
- SillyTavern installation

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/stcm.git
cd stcm

# Install dependencies
pip install -r backend/requirements.txt

# Copy and edit configuration
cp config.example.yaml config.yaml
nano config.yaml  # Edit your SillyTavern paths and Ollama settings

# Initialize database
python backend/init_db.py

# Run the server
python backend/main.py
```

Open your browser to `http://localhost:7847`

---

## Configuration

Edit `config.yaml`:

```yaml
ollama:
  url: "http://localhost:11434"
  model: "llama3.2"  # or mistral, qwen2.5, etc.

sillytavern:
  chats_dir: "/path/to/SillyTavern/data/default-user/chats"
  characters_dir: "/path/to/SillyTavern/data/default-user/characters"
  personas_dir: "/path/to/SillyTavern/data/default-user/personas"

scanning:
  schedule: "0 3 * * *"  # Daily at 3 AM
  messages_per_scan: 50
```

### Chat-to-Lorebook Mapping

In the Settings page, configure which chat files use which character lorebooks:

```
Jinx_Campaign.jsonl → Jinx.json (Aerthos lorebook)
SciFi_Adventure.jsonl → Cortex.json (Cyberpunk lorebook)
```

This ensures entities are added to the correct campaign's lorebook.

---

## Usage

### 1. Manual Scan

Click "Run Manual Scan" on the dashboard to scan recent messages.

### 2. Review Entities

New entities appear in the Review Queue:
- **Green (high confidence)** - LLM is very confident
- **Yellow (medium)** - May need review
- **Red (low confidence)** - Definitely review before applying

### 3. Approve or Edit

- Click **Approve** to add to lorebook
- Click **Edit** to modify before adding
- Click **Reject** to dismiss

### 4. Automatic Scans

Enable scheduled scans in Settings to run automatically.

---

## How It Works

```
1. STCM reads your chat logs (.jsonl files)
2. Sends recent messages to Ollama
3. Ollama extracts NPCs, factions, locations, items, aliases
4. STCM presents them in the review queue
5. You approve/edit/reject
6. STCM updates your character lorebook JSON
7. SillyTavern automatically uses updated lorebook in next chat
```

---

## Entity Types

### NPCs
- Name, appearance, role
- Relationship to player
- Auto-added to lorebook with proper keys

### Factions
- Name, description, goals
- Leadership, territory
- Relationship status (ally/enemy/neutral)

### Locations
- Name, description
- Significance to campaign

### Items
- Name, properties
- Magical effects

### Character Aliases
- Auto-detects when player uses disguises
- Updates persona with new identities
- Example: "Draven Martell" alias for "The Raven"

### Stats/Equipment (Persona Updates)
- HP changes
- Gold tracking
- Level ups
- New equipment

---

## Prompts

STCM uses carefully crafted prompts in `/prompts/`:

- `entity_extraction.txt` - Main extraction prompt
- `npc_analysis.txt` - Deep NPC analysis
- `faction_analysis.txt` - Faction details
- `persona_update.txt` - Character updates

You can edit these to customize what STCM looks for!

---

## Backups

STCM **always** creates backups before modifying files:

```
data/backups/
├── Jinx__2_.json.2026-02-13_15-30-22.backup
├── Jinx__2_.json.2026-02-13_16-45-10.backup
└── personas.json.2026-02-13_15-30-22.backup
```

Restore from Settings > File Management > Backups

---

## API Documentation

Once running, visit `http://localhost:7847/docs` for interactive API documentation.

---

## Troubleshooting

### "Ollama connection failed"
- Ensure Ollama is running: `ollama serve`
- Check URL in config.yaml
- Test with: `curl http://localhost:11434/api/tags`

### "No entities found"
- Check your Ollama model is downloaded: `ollama pull llama3.2`
- Try lowering confidence threshold in settings
- Review prompts in `/prompts/` - may need adjustment

### "File permission denied"
- Ensure STCM has read access to chat logs
- Ensure write access to characters/personas directories

### "Duplicate entries"
- STCM checks for duplicates by name
- If detected, it merges information instead of creating duplicates

---

## Development

### Project Structure

```
stcm/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── database.py          # SQLite operations
│   ├── scheduler.py         # Cron jobs
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── services/
│   │   ├── ollama_client.py
│   │   ├── entity_extractor.py
│   │   └── lorebook_updater.py
│   └── utils/
│       └── file_ops.py      # Safe file operations
├── frontend/
│   ├── index.html           # Dashboard
│   ├── settings.html        # Configuration
│   └── review.html          # Review queue
└── data/
    ├── stcm.db             # SQLite database
    └── backups/            # File backups
```

### Running Tests

```bash
pytest backend/tests/
```

### Contributing

Pull requests welcome! Please:
1. Add tests for new features
2. Update documentation
3. Follow existing code style

---

## Future Enhancements

- **Multi-campaign dashboard** - Switch between campaigns easily
- **Export campaign summary** - Generate markdown session recaps
- **Foundry VTT integration** - Sync with virtual tabletop
- **Voice-to-text** - Process session recordings
- **Character relationship graphs** - Visualize NPC connections
- **Automatic session summaries** - LLM-generated recaps
- **Mobile app** - Manage on the go
- **Cloud sync** - Sync between devices
- **Advanced conflict resolution** - Smart merging of duplicate entities
- **Analytics dashboard** - Campaign statistics and insights
- **Batch operations** - Approve/reject multiple entities at once
- **Custom entity types** - Define your own trackable elements
- **Quest/story arc tracking** - Manage ongoing plotlines
- **Faction relationship matrix** - Track inter-faction dynamics

---

## License

MIT License - see LICENSE file

---

## Credits

Created for the SillyTavern community ❤️

Powered by:
- [FastAPI](https://fastapi.tiangolo.com/)
- [Ollama](https://ollama.ai/)
- [SQLite](https://www.sqlite.org/)

---

## Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/stcm/issues)
- **Discord:** [SillyTavern Discord](https://discord.gg/sillytavern)

---

**Happy campaigning! 🎲**
