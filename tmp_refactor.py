import re
import sys

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    content = re.sub(r'from sqlalchemy\.orm import Session as DBSession', 'from sqlalchemy.ext.asyncio import AsyncSession\nfrom sqlalchemy import select, func\nfrom sqlalchemy.orm import selectinload', content)
    content = content.replace(': DBSession = Depends', ': AsyncSession = Depends')
    content = content.replace('def get_admin_dashboard(', 'async def get_admin_dashboard(')
    content = content.replace('def get_users(', 'async def get_users(')
    content = content.replace('def update_user_role(', 'async def update_user_role(')
    content = content.replace('def delete_user(', 'async def delete_user(')
    content = content.replace('def update_admin_settings(', 'async def update_admin_settings(')
    content = content.replace('def get_sessions(', 'async def get_sessions(')
    content = content.replace('def create_session(', 'async def create_session(')
    content = content.replace('def get_session(', 'async def get_session(')
    content = content.replace('def update_session_status(', 'async def update_session_status(')
    content = content.replace('def get_session_participants(', 'async def get_session_participants(')
    content = content.replace('def get_session_messages(', 'async def get_session_messages(')
    content = content.replace('def get_leaderboard(', 'async def get_leaderboard(')
    content = content.replace('def get_notifications(', 'async def get_notifications(')
    content = content.replace('def get_audit_logs(', 'async def get_audit_logs(')

    # N+1 fixing
    content = content.replace(
        'participants = (\n        db.query(UserSession)\n        .filter(UserSession.session_id == session_id)\n        .order_by(UserSession.score.desc())\n        .all()\n    )',
        'participants = (\n        await db.execute(\n            select(UserSession)\n            .filter(UserSession.session_id == session_id)\n            .options(selectinload(UserSession.user))\n            .order_by(UserSession.score.desc())\n        )\n    ).scalars().all()'
    )
    content = content.replace('user = db.query(User).filter(User.id == us.user_id).first()', '')
    content = content.replace('        if user:\n            user_name = user.name\n            user_email = user.email', '        user_name = us.user.name if us.user else "Unknown"\n        user_email = us.user.email if us.user else "Unknown"')

    content = content.replace(
        'leaderboard = (\n        db.query(UserSession)\n        .filter(UserSession.session_id == session_id)\n        .order_by(UserSession.score.desc(), UserSession.joined_at.asc())\n        .all()\n    )',
        'leaderboard = (\n        await db.execute(\n            select(UserSession)\n            .filter(UserSession.session_id == session_id)\n            .options(selectinload(UserSession.user))\n            .order_by(UserSession.score.desc(), UserSession.joined_at.asc())\n        )\n    ).scalars().all()'
    )
    content = content.replace('        if user:\n            name = user.name', '        name = us.user.name if us.user else "Unknown"')
    content = content.replace('            user_name = user.name\n', '')

    # Simple queries
    content = re.sub(r'db\.query\((\w+)\)\.filter\((.+?)\)\.first\(\)', r'(await db.execute(select(\1).filter(\2))).scalars().first()', content)
    content = re.sub(r'db\.query\((\w+)\)\.filter\((.+?)\)\.all\(\)', r'(await db.execute(select(\1).filter(\2))).scalars().all()', content)
    content = re.sub(r'db\.query\((\w+)\)\.order_by\((.+?)\)\.all\(\)', r'(await db.execute(select(\1).order_by(\2))).scalars().all()', content)
    content = re.sub(r'db\.query\((\w+)\)\.order_by\((.+?)\)\.limit\((.+?)\)\.all\(\)', r'(await db.execute(select(\1).order_by(\2).limit(\3))).scalars().all()', content)
    content = re.sub(r'db\.query\((\w+)\)\.first\(\)', r'(await db.execute(select(\1))).scalars().first()', content)
    content = re.sub(r'db\.query\((\w+)\)\.count\(\)', r'(await db.execute(select(func.count()).select_from(\1))).scalar()', content)
    content = re.sub(r'db\.query\((.+?)\)\.filter\((.+?)\)\.count\(\)', r'(await db.execute(select(func.count()).select_from(Message).filter(\2))).scalar()', content)
    content = re.sub(r'db\.query\((.+?)\)\.scalar\(\)', r'(await db.execute(select(\1))).scalar()', content)

    # Commits
    content = content.replace('db.commit()', 'await db.commit()')
    content = content.replace('db.refresh', 'await db.refresh')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

refactor_file("c:/Users/PRANAV M K/blackbox/blackBox/backend/app/routes/admin.py")
