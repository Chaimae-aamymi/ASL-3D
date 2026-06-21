"""
report_generator.py — PDF Report Generation using fpdf2
Generates a professional, structured restoration report with absolute layout stability.
"""
from __future__ import annotations
import os
from datetime import datetime
from fpdf import FPDF

def generate_report(output_path: str, engineer_name: str, project, analysis, plan: dict = None, impact: dict = None, urban_impact: dict = None) -> str:
    """
    Generate an ultra-premium restoration report with absolute header-to-content separation.
    """
    # ── Design Tokens ─────────────────────────────────────────────────
    BRAND_NAVY   = (15, 23, 42)
    BRAND_ACCENT  = (99, 102, 241)
    BRAND_GRAY    = (100, 116, 139)
    TEXT_MAIN     = (30, 41, 59)
    BG_CARD       = (248, 250, 252)
    BORDER_COLOR  = (226, 232, 240)

    # ── Resources ─────────────────────────────────────────────────────
    upload_base  = os.path.join('static', 'uploads')
    folder       = os.path.join(upload_base, project.upload_folder)
    photo_path   = None
    if os.path.exists(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.jfif')):
                photo_path = os.path.join(folder, fname)
                break

    annotated_path = None
    if analysis.annotated_image:
        ap = os.path.join('static', 'analyses', 'results', analysis.annotated_image)
        if os.path.exists(ap): annotated_path = ap

    # ── Risk Assessment ────────────────────────────────────────────────
    score = float(analysis.risk_score or 0)
    if score >= 70:
        risk_color = (220, 38, 38)
        status_text = 'NÉCESSITÉ D\'INTERVENTION URGENTE'
    elif score >= 40:
        risk_color = (217, 119, 6)
        status_text = 'INTERVENTION PLANIFIÉE'
    else:
        risk_color = (22, 163, 74)
        status_text = 'ENTRETIEN RÉGULIER'

    # ═══════════════════════════════════════════════════════════════════
    # PDF Core Class (Absolute Scaling)
    # ═══════════════════════════════════════════════════════════════════
    class ASLReport(FPDF):
        def header(self):
            h_h = 35 if self.page_no() == 1 else 15
            # Draw header bar and accent line
            self.set_fill_color(*BRAND_NAVY)
            self.rect(0, 0, 210, h_h, 'F')
            self.set_fill_color(*BRAND_ACCENT)
            self.rect(0, h_h, 210, 1.2, 'F')
            
            self.set_text_color(255, 255, 255)
            # DO NOT USE set_y/set_xy in header, use text() to avoid cursor movement
            if self.page_no() == 1:
                self.set_font('Arial', 'B', 22)
                self.text(90, 18, 'ASL-3D')
                self.set_font('Arial', '', 10)
                self.text(55, 28, 'EXPERTISE TECHNIQUE ET PROTOCOLE DE RESTAURATION')
            else:
                self.set_font('Arial', 'B', 10)
                self.text(70, 10, 'ASL-3D - Evaluation Technique du Patrimoine')

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(*BRAND_GRAY)
            self.cell(0, 10, f'Confidentiel ASL-3D  |  Généré le {datetime.now().strftime("%d/%m/%Y")}  |  Page {self.page_no()}', align='C')

        def section_title(self, title: str):
            self.ln(10)
            self.set_font('Arial', 'B', 14)
            self.set_text_color(*BRAND_NAVY)
            self.cell(0, 8, title.upper(), ln=1)
            self.set_draw_color(*BRAND_ACCENT)
            self.set_line_width(0.7)
            self.line(self.l_margin, self.get_y()-1, self.l_margin + 25, self.get_y()-1)
            self.set_line_width(0.2)
            self.ln(2)

    pdf = ASLReport()
    
    # Fonts
    sys_arial = r"C:\Windows\Fonts\arial.ttf"
    sys_arial_bd = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(sys_arial):
        pdf.add_font("Arial", "", sys_arial)
        if os.path.exists(sys_arial_bd):
            pdf.add_font("Arial", "B", sys_arial_bd)
    
    # SAFE MARGINS: 35mm top margin ensures no text overlap on Page 2+ (Header=15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 35, 20)
    pdf.add_page()
    # Content start below Header (35 for page 1 + 15 cushion = 50)
    pdf.set_y(50)

    # 1. Metric Cards
    pdf.section_title('1. Résumé Exécutif')
    curr_y = pdf.get_y()
    card_w = 54
    gap = 4
    
    def metric(x, y, label, value, val_color):
        pdf.set_fill_color(*BG_CARD)
        pdf.rect(x, y, card_w, 25, 'F')
        pdf.set_draw_color(*BORDER_COLOR)
        pdf.rect(x, y, card_w, 25, 'D')
        pdf.set_xy(x, y + 4)
        pdf.set_font('Arial', 'B', 7)
        pdf.set_text_color(*BRAND_GRAY)
        pdf.cell(card_w, 4, label, align='C', ln=1)
        pdf.set_x(x)
        pdf.set_font('Arial', 'B', 15)
        pdf.set_text_color(*val_color)
        pdf.cell(card_w, 10, value, align='C', ln=1)

    metric(20, curr_y, 'SCORE DE RISQUE IA', f'{int(score)}/100', risk_color)
    num_deg = len(analysis.degradations or [])
    metric(20 + card_w + gap, curr_y, 'ANOMALIES DÉTECTÉES', str(num_deg), TEXT_MAIN)
    dur_text = plan['summary']['estimated_duration'] if plan else 'N/A'
    metric(20 + (card_w + gap)*2, curr_y, 'DURÉE ESTIMÉE', dur_text, TEXT_MAIN)
    
    pdf.set_y(curr_y + 32)

    # 2. Informations Générales
    pdf.section_title('2. Informations Générales')
    pdf.set_font('Arial', '', 9)
    def data_row(label, val):
        pdf.set_fill_color(252, 253, 255)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(*BRAND_GRAY)
        pdf.cell(60, 8, f" {label}", border='B', fill=True)
        pdf.set_text_color(*TEXT_MAIN)
        pdf.set_font('Arial', '', 9)
        pdf.cell(0, 8, f" {val}", border='B', ln=1)

    data_row('Monument Analysé',   project.monument)
    data_row('Cadre Géographique', project.location or 'Non spécifiée')
    data_row('Expert Responsable',   engineer_name)
    data_row('Date de Rapport',    datetime.now().strftime('%d/%m/%Y'))

    # 3. Expertise Technique Visuelle
    pdf.section_title('3. Expertise Technique Visuelle')
    if photo_path:
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*BRAND_NAVY)
        pdf.cell(0, 7, ' Documentation Photographique Initiale', ln=1)
        pdf.image(photo_path, w=145)
        pdf.ln(5)

    if annotated_path:
        pdf.add_page() # ALWAYS force Page 2 for heavy visual analysis to avoid header overlap during auto-break
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*BRAND_NAVY)
        pdf.cell(0, 7, ' Cartographie des désordres (YOLOv8)', ln=1)
        pdf.image(annotated_path, w=145)
        pdf.ln(8)

    if analysis.degradations:
        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(*BRAND_NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(70, 10, ' Typologie Pathologique', fill=True)
        pdf.cell(40, 10, ' Sévérité', align='C', fill=True)
        pdf.cell(60, 10, ' Confiance IA', align='C', fill=True, ln=1)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*TEXT_MAIN)
        unique_degs = []
        seen = set()
        for d in analysis.degradations:
            key = (d.get('type',''), d.get('severity',''))
            if key not in seen:
                unique_degs.append(d)
                seen.add(key)
        for d in unique_degs:
            pdf.cell(70, 9, ' ' + str(d.get('type','?')).capitalize(), border='B')
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(40, 9, str(d.get('severity','?')).upper(), border='B', align='C')
            pdf.set_font('Arial', '', 9)
            conf = float(d.get('confidence',0))
            pdf.cell(60, 9, f'{conf*100:.1f}%', border='B', align='C', ln=1)

    # 4. Analyse d'Impact Infrastructure (Nouveau)
    if impact:
        pdf.add_page()
        pdf.section_title('4. Analyse d\'Impact d\'Infrastructure')
        
        # Project Summary Card
        pdf.set_fill_color(*BG_CARD)
        pdf.rect(pdf.l_margin, pdf.get_y(), 170, 20, 'F')
        pdf.set_draw_color(*BORDER_COLOR)
        pdf.rect(pdf.l_margin, pdf.get_y(), 170, 20, 'D')
        
        pdf.set_xy(pdf.l_margin + 5, pdf.get_y() + 4)
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*BRAND_NAVY)
        pdf.cell(100, 5, f" PROJET : {str(impact.get('project', 'N/A')).upper()}")
        
        pdf.set_x(pdf.l_margin + 120)
        pdf.set_font('Arial', 'B', 9)
        impact_risk_color = impact.get('risk_color', (217, 119, 6))
        pdf.set_text_color(*impact_risk_color)
        pdf.cell(45, 5, f"RISQUE : {impact.get('risk_level', 'N/A')}", align='R', ln=1)
        
        pdf.set_x(pdf.l_margin + 5)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(*BRAND_GRAY)
        desc = impact.get('description', '')
        pdf.cell(0, 5, f"Description : {desc[:80]}..." if len(desc) > 80 else f"Description : {desc}")
        pdf.ln(12)

        # Concerns
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*BRAND_NAVY)
        pdf.cell(0, 8, 'Points de Vigilance Majeurs', ln=1)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*TEXT_MAIN)
        for concern in impact.get('main_concerns', []):
            pdf.set_x(pdf.l_margin + 5)
            pdf.cell(5, 6, "-", ln=0)
            pdf.multi_cell(160, 6, concern)
        pdf.ln(4)

        # Engineering Advice
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*BRAND_ACCENT)
        pdf.cell(0, 8, 'Conseils Techniques aux Ingénieurs', ln=1)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*TEXT_MAIN)
        for advice in impact.get('engineering_advice', []):
            pdf.set_x(pdf.l_margin + 5)
            pdf.set_text_color(*BRAND_ACCENT)
            pdf.cell(5, 6, chr(187), ln=0)
            pdf.set_text_color(*TEXT_MAIN)
            pdf.multi_cell(160, 6, advice)
        pdf.ln(5)

    # 5. Plan de Restauration
    if plan and plan.get('phases'):
        section_num = 4 + (1 if impact else 0)
        pdf.section_title(f'{section_num}. Plan de Restauration Preconise')
        for phase in plan['phases']:
            pdf.set_fill_color(*BRAND_NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 9, f" PHASE {phase['phase']} : PROCÉDÉ DE {phase['type'].upper()}", fill=True, ln=1)
            pdf.ln(2)
            pdf.set_text_color(*TEXT_MAIN)
            pdf.set_font('Arial', 'B', 9)
            pdf.write(7, ' Durée estimée : ')
            pdf.set_font('Arial', '', 9)
            pdf.write(7, str(phase['duration']))
            pdf.ln(10)
            for step in phase.get('steps', []):
                pdf.set_x(25)
                pdf.set_text_color(*BRAND_ACCENT)
                pdf.cell(5, 6, chr(187))
                pdf.set_text_color(*TEXT_MAIN)
                pdf.multi_cell(140, 6, step)
            pdf.ln(5)

    # Urban Impact Section (from urban-assessment route)
    if urban_impact:
        pdf.add_page()
        pdf.section_title('Impact des Projets Connexes')
        rc = urban_impact.get('risk_color', (217, 119, 6))
        vi = urban_impact.get('v_impact', 0)
        rl = urban_impact.get('risk_label', 'N/A')
        vs = urban_impact.get('v_source', 15)
        k  = urban_impact.get('k', 0.025)
        dm = urban_impact.get('distance_m', 100)
        tl = urban_impact.get('type_label', 'Infrastructure')

        # Summary Card
        pdf.set_fill_color(*BG_CARD)
        pdf.rect(pdf.l_margin, pdf.get_y(), 170, 22, 'F')
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*BRAND_NAVY)
        pdf.set_xy(pdf.l_margin + 5, pdf.get_y() + 5)
        pdf.cell(90, 6, f' Projet: {tl}  |  Distance: {int(dm)}m')
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*rc)
        pdf.set_x(pdf.l_margin + 120)
        pdf.cell(45, 6, f'RISQUE: {rl}', align='R', ln=1)
        pdf.ln(8)

        # Formula
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(*BRAND_GRAY)
        pdf.cell(0, 6, f'Formule: V_impact = {vs} x e^(-{k} x {int(dm)}) = {round(vi,4)} mm/s', ln=1)
        pdf.ln(4)

        # Boost Warning
        if urban_impact.get('severity_boost'):
            pdf.set_fill_color(220, 38, 38)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 8, ' ALERTE: Fissures detectees + Proximite < 50m - Severite boostee a CRITIQUE', fill=True, ln=1)
            pdf.ln(4)

        # Recommendations
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(*BRAND_NAVY)
        pdf.cell(0, 7, 'Recommandations Techniques:', ln=1)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*TEXT_MAIN)
        for rec in urban_impact.get('recommendations', []):
            if rec.strip():
                pdf.set_x(pdf.l_margin + 5)
                pdf.set_text_color(*BRAND_ACCENT)
                pdf.cell(5, 6, chr(187), ln=0)
                pdf.set_text_color(*TEXT_MAIN)
                pdf.multi_cell(155, 6, rec)
        pdf.ln(5)

    # Conclusion
    pdf.ln(10)
    pdf.set_fill_color(*BRAND_NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 12, ' VERDICT FINAL & ÉTHIQUE DU PATRIMOINE', fill=True, ln=1)
    pdf.ln(4)
    pdf.set_text_color(*TEXT_MAIN)
    pdf.set_font('Arial', 'B', 10)
    pdf.write(8, 'Synthèse d\'Expert : ')
    pdf.set_text_color(*risk_color)
    pdf.write(8, status_text)
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(*BRAND_GRAY)
    pdf.multi_cell(0, 5, "Ce document constitue une attestation technique d'ASL-3D. Toutes les détections YOLOv8 doivent être vérifiées in situ par l'équipe technique.")

    # ── Output ────────────────────────────────────────────────────────
    pdf.output(output_path)
    return output_path
