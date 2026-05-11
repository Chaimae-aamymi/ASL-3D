
import os

def repair_double_encoding(file_path):
    try:
        # Read as UTF-8
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to fix by encoding to latin-1 and decoding back to utf-8
        # This is the standard fix for UTF-8 interpreted as Latin-1 then saved as UTF-8
        try:
            repaired = content.encode('latin-1').decode('utf-8')
            if repaired != content:
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(repaired)
                return "REPAIRED"
        except (UnicodeEncodeError, UnicodeDecodeError):
            # If this fails, it might not be double-encoded, or it has characters outside Latin-1
            # Fallback to manual replacement for specific remaining issues
            mapping = {
                'Ã\xa0': 'à',
                'Ã\u00a0': 'à',
                'Ã\u2030': 'É',
                'Ã\u0089': 'É',
                'Ã\u00a9': 'é',
                'Ã\u00aa': 'ê',
                'Ã\u00ab': 'ë',
                'Ã\u00ae': 'î',
                'Ã\u00af': 'ï',
                'Ã\u00b4': 'ô',
                'Ã\u00bb': 'û',
                'Ã\u00a7': 'ç',
                'â\u0080\u0094': '—',
                'â\u0080\u0099': "'"
            }
            new_content = content
            for bad, good in mapping.items():
                new_content = new_content.replace(bad, good)
            
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(new_content)
                return "FIXED_MANUAL"
            
        return "ALREADY_CLEAN"
    except Exception as e:
        return f"ERROR: {str(e)}"

templates_dir = 'templates'
for fname in os.listdir(templates_dir):
    if fname.endswith('.html'):
        fpath = os.path.join(templates_dir, fname)
        result = repair_double_encoding(fpath)
        print(f"{result}: {fname}")

print("Vérification terminée.")
