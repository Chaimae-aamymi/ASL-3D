
import os

def fix_mojibake(content):
    # Mapping common double-encoded UTF-8 sequences back to characters
    mapping = {
        'Ã©': 'é',
        'Ã ': 'à',
        'Ã¨': 'è',
        'Ã«': 'ë',
        'Ã®': 'î',
        'Ã´': 'ô',
        'Ã»': 'û',
        'Ãª': 'ê',
        'Ã§': 'ç',
        'Ã€': 'À',
        'Ã‰': 'É',
        'Ã\u00af': 'ï',
        'â\u0080\u0094': '—',
        'â\u0080\u0099': "'",
        'â\u0080\u00a6': '...'
    }
    for bad, good in mapping.items():
        content = content.replace(bad, good)
    return content

templates_dir = 'templates'
for fname in os.listdir(templates_dir):
    if fname.endswith('.html'):
        fpath = os.path.join(templates_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            fixed_content = fix_mojibake(content)
            
            if fixed_content != content:
                with open(fpath, 'w', encoding='utf-8', newline='') as f:
                    f.write(fixed_content)
                print(f'FIXED: {fname}')
            else:
                print(f'CLEAN: {fname}')
        except Exception as e:
            print(f'ERROR on {fname}: {e}')

print("Nettoyage terminé.")
