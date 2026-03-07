# Setup Guide - Degradation Detector App

## GitHub Configuration

### 1. Configure Git Credentials

Run these commands in PowerShell:

```powershell
git config --global user.name "Chaimae Aamymi"
git config --global user.email "aamymichaimae05@gmail.com"
```

### 2. Initialize Git Repository

```powershell
cd C:\Users\HP\pfe\app
git init
```

### 3. Add All Files

```powershell
git add .
```

### 4. Create Initial Commit

```powershell
git commit -m "Initial commit: Degradation Detector App"
```

### 5. Add Remote Repository

```powershell
git remote add origin https://github.com/Chaimae-aamymi/ASL-3D.git
```

### 6. Push to GitHub (Replace Content)

```powershell
git push -u origin main --force
```

If you get an error about branch names, try:

```powershell
git push -u origin master --force
```

## Troubleshooting

- **Authentication Error**: Use GitHub Personal Access Token
  - Go to: https://github.com/settings/tokens
  - Create new token with `repo` scope
  - Use token as password when prompted

- **Branch Not Found**: Check your repository default branch:
  - Go to: https://github.com/Chaimae-aamymi/ASL-3D/settings
  - Look for "Default branch" setting

## Files Included

- `degradation_detector.py` - Main detection engine
- `icons.py` - Professional icon management
- `requirements.txt` - Dependencies
- `.gitignore` - Git ignore rules
- `README.md` - Project documentation
