"""
Professional Icon Management for Degradation Detector App
Uses Unicode symbols and styling for a professional appearance
"""

class Icons:
    """Professional icon set for the application"""
    
    # Navigation & UI Icons
    HOME = "🏠"
    SETTINGS = "⚙️"
    BACK = "◀️"
    NEXT = "▶️"
    CLOSE = "✕"
    MENU = "☰"
    SEARCH = "🔍"
    
    # Detection & Analysis Icons
    CAMERA = "📷"
    IMAGE = "🖼️"
    ANALYSIS = "📊"
    DETECT = "🎯"
    SCAN = "📡"
    
    # Degradation Types Icons
    FISSURES = '<i class="ph-duotone ph-asterisk"></i>'
    HUMIDITY = '<i class="ph-duotone ph-drop"></i>'
    EROSION = '<i class="ph-duotone ph-wind"></i>'
    FUNGI = '<i class="ph-duotone ph-plant"></i>'
    DISCOLORATION = '<i class="ph-duotone ph-palette"></i>'
    CRUMBLING = '<i class="ph-duotone ph-hammer"></i>'
    
    # Status Icons
    SUCCESS = '<i class="ph-fill ph-check-circle"></i>'
    ERROR = '<i class="ph-fill ph-x-circle"></i>'
    WARNING = '<i class="ph-fill ph-warning"></i>'
    INFO = '<i class="ph-fill ph-info"></i>'
    LOADING = '<i class="ph-duotone ph-hourglass-high"></i>'
    
    # Severity Icons
    CRITICAL = '<i class="ph-fill ph-circle" style="color:var(--accent-3);"></i>'
    HIGH = '<i class="ph-fill ph-circle" style="color:#ff9f1c;"></i>'
    MEDIUM = '<i class="ph-fill ph-circle" style="color:var(--accent-2);"></i>'
    LOW = '<i class="ph-fill ph-circle" style="color:var(--accent-primary);"></i>'
    
    # Actions
    SAVE = '<i class="ph-bold ph-floppy-disk"></i>'
    LOAD = '<i class="ph-bold ph-folder-open"></i>'
    EXPORT = '<i class="ph-bold ph-export"></i>'
    IMPORT = '<i class="ph-bold ph-download-simple"></i>'
    PRINT = '<i class="ph-bold ph-printer"></i>'
    DELETE = '<i class="ph-bold ph-trash"></i>'
    EDIT = '<i class="ph-bold ph-pencil-simple"></i>'
    
    # Reports
    REPORT = '<i class="ph-duotone ph-clipboard-text"></i>'
    PDF = '<i class="ph-duotone ph-file-pdf"></i>'
    CHART = '<i class="ph-duotone ph-chart-bar"></i>'
    TABLE = '<i class="ph-duotone ph-table"></i>'
    
    # System
    BELL = '<i class="ph-duotone ph-bell"></i>'
    HELP = '<i class="ph-duotone ph-question"></i>'
    USER = '<i class="ph-duotone ph-user"></i>'
    LOGOUT = '<i class="ph-duotone ph-sign-out"></i>'

class IconColors:
    """Professional color codes for icons"""
    
    # RGB Color Codes
    CRITICAL = (255, 0, 0)      # Red
    HIGH = (255, 165, 0)        # Orange
    MEDIUM = (255, 255, 0)      # Yellow
    LOW = (0, 128, 0)           # Green
    
    # UI Colors
    PRIMARY = (33, 150, 243)    # Blue
    SECONDARY = (76, 175, 80)   # Green
    ACCENT = (255, 152, 0)      # Orange
    NEUTRAL = (158, 158, 158)   # Gray
    
    # Status Colors
    SUCCESS = (76, 175, 80)     # Green
    ERROR = (244, 67, 54)       # Red
    WARNING = (255, 152, 0)     # Orange
    INFO = (33, 150, 243)       # Blue

class IconText:
    """Professional text labels for icons"""
    
    DEGRADATION_TYPES = {
        'fissures': f"{Icons.FISSURES} Fissures",
        'humidite': f"{Icons.HUMIDITY} Humidité",
        'erosion': f"{Icons.EROSION} Érosion",
        'champignons': f"{Icons.FUNGI} Champignons",
        'decoloration': f"{Icons.DISCOLORATION} Décoloration",
        'effritement': f"{Icons.CRUMBLING} Effritement"
    }
    
    SEVERITY_LEVELS = {
        'critique': f"{Icons.CRITICAL} CRITIQUE",
        'haute': f"{Icons.HIGH} HAUTE",
        'moyenne': f"{Icons.MEDIUM} MOYENNE",
        'faible': f"{Icons.LOW} FAIBLE"
    }
    
    STATUS = {
        'success': f"{Icons.SUCCESS} Succès",
        'error': f"{Icons.ERROR} Erreur",
        'warning': f"{Icons.WARNING} Avertissement",
        'info': f"{Icons.INFO} Information",
        'loading': f"{Icons.LOADING} Traitement..."
    }
    
    ACTIONS = {
        'save': f"{Icons.SAVE} Enregistrer",
        'load': f"{Icons.LOAD} Charger",
        'export': f"{Icons.EXPORT} Exporter",
        'import': f"{Icons.IMPORT} Importer",
        'delete': f"{Icons.DELETE} Supprimer",
        'edit': f"{Icons.EDIT} Modifier"
    }
