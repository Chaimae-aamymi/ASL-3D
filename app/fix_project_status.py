"""
One-time fix: update projects stuck as 'nouveau' that already have a completed analysis.
Run: python fix_project_status.py
"""
from app import app, db
from models import Project, Analysis

with app.app_context():
    projects = Project.query.all()
    updated = 0
    for p in projects:
        latest = p.latest_analysis
        if latest and p.status == 'nouveau':
            if latest.status_update == 'Danger':
                p.status = 'danger'
            elif latest.status_update == 'Attention':
                p.status = 'en_cours'
            else:
                p.status = 'termine'
            updated += 1
            print(f"  Project ID={p.id} \"{p.name}\" => status now: {p.status} (analysis={latest.status_update})")
    if updated:
        db.session.commit()
        print(f"\nDone. Updated {updated} project(s).")
    else:
        print("No stuck projects found. All project statuses are already correct.")

    print("\nAll projects:")
    for p in Project.query.all():
        a = p.latest_analysis
        print(f"  ID={p.id}  status={p.status:<10}  has_analysis={a is not None}  name={p.name}")
