
#!/usr/bin/env python3
import shutil, datetime
shutil.copy('bot.db', f'backup_{datetime.datetime.now().isoformat()}.db')
