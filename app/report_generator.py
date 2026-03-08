"""
report_generator.py — PDF Report Generation using fpdf2
Generates a professional restoration report for ASL-3D projects.
"""
from __future__ import annotations
import os
from datetime import datetime


def generate_report(output_path: str, engineer_name: str, project, analysis) -> str:
    """
    Generate a PDF restoration report.

    Args:
        output_path  : Full path where the PDF will be saved.
        engineer_name: Name of the logged-in engineer.
        project      : SQLAlchemy Project instance.
        analysis     : SQLAlchemy Analysis instance.

    Returns:
        output_path (str)
    """
    from fpdf import FPDF

    # ── Resolve monument photo ─────────────────────────────────────────
    upload_base  = os.path.join('static', 'uploads')
    folder       = os.path.join(upload_base, project.upload_folder)
    photo_path   = None
    if os.path.exists(folder):
        for fname in os.listdir(folder):
            ext = fname.rsplit('.', 1)[-1].lower()
            if ext in ('jpg', 'jpeg', 'png'):
                photo_path = os.path.join(folder, fname)
                break

    # ── Annotated image path ────────────────────────────────────────────
    annotated_path = None
    if analysis.annotated_image:
        ap = os.path.join('outputs', analysis.annotated_image)
        if os.path.exists(ap):
            annotated_path = ap

    # ── Score and color ────────────────────────────────────────────────
    score = float(analysis.risk_score or 0)
    if score >= 70:
        risk_color = (220, 50, 50)
        risk_label = 'DANGER'
    elif score >= 40:
        risk_color = (230, 160, 40)
        risk_label = 'ATTENTION'
    else:
        risk_color = (30, 180, 100)
        risk_label = 'SAIN'

    # ── Recommendations ────────────────────────────────────────────────
    rec_text = analysis.recommendations or 'Aucune recommandation spécifique.'

    # ═══════════════════════════════════════════════════════════════════
    # Build PDF
    # ═══════════════════════════════════════════════════════════════════
    class ASLReport(FPDF):
        def header(self):
            # Background header band
            self.set_fill_color(15, 21, 32)
            self.rect(0, 0, 210, 30, 'F')
            self.set_text_color(232, 236, 244)
            self.set_font('Helvetica', 'B', 18)
            self.set_y(8)
            self.cell(0, 10, 'ASL-3D  —  Rapport de Restauration', align='C')
            self.set_font('Helvetica', '', 8)
            self.set_text_color(138, 148, 168)
            self.ln(8)
            self.cell(0, 5, 'Restauration Numérique Intelligente de Bâtiments Historiques', align='C')
            self.ln(10)

        def footer(self):
            self.set_y(-12)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(138, 148, 168)
            self.cell(0, 10, f'Page {self.page_no()}  |  Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')

        def section_title(self, title: str):
            self.ln(6)
            self.set_fill_color(22, 28, 45)
            self.set_text_color(108, 99, 255)
            self.set_font('Helvetica', 'B', 12)
            self.cell(0, 8, f'  {title}', fill=True)
            self.ln(4)
            self.set_text_color(30, 30, 30)

        def key_value(self, key: str, value: str):
            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(60, 60, 80)
            self.cell(55, 7, key + ' :')
            self.set_font('Helvetica', '', 10)
            self.set_text_color(30, 30, 30)
            self.multi_cell(0, 7, str(value))

    pdf = ASLReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 35, 15)
    pdf.add_page()

    # ── Section 1 : Project Information ───────────────────────────────
    pdf.section_title('1. Informations du Projet')
    pdf.key_value('Ingénieur',   engineer_name)
    pdf.key_value('Projet',      project.name)
    pdf.key_value('Monument',    project.monument)
    if project.location:
        pdf.key_value('Localisation', project.location)
    if project.description:
        pdf.key_value('Description',  project.description)
    pdf.key_value('Date',       datetime.now().strftime('%d/%m/%Y'))
    pdf.key_value('Statut',     project.status.upper())

    # ── Section 2 : Monument Photo ─────────────────────────────────────
    if photo_path:
        pdf.section_title('2. Photo du Monument')
        try:
            # Center image
            img_w = 120
            x_pos = (210 - img_w) / 2
            pdf.image(photo_path, x=x_pos, w=img_w)
            pdf.ln(4)
        except Exception:
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 8, '(Image non disponible)')
            pdf.ln(4)

    # ── Section 3 : AI Score ───────────────────────────────────────────
    pdf.section_title('3. Score de Risque IA (YOLOv8)')
    pdf.ln(3)

    # Score badge
    pdf.set_fill_color(*risk_color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 22)
    pdf.cell(60, 16, f'  {int(score)} / 100', fill=True, align='C')
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(40, 16, f'  {risk_label}', fill=True)
    pdf.ln(8)

    pdf.set_text_color(30, 30, 30)
    pdf.set_font('Helvetica', '', 10)
    pdf.key_value('Modèle IA',   analysis.model_used or 'YOLOv8')
    pdf.key_value('Sévérité',    (analysis.severity or '').upper())
    pdf.key_value('Statut',      analysis.status_update or 'N/A')
    pdf.key_value('Date analyse', analysis.created_at.strftime('%d/%m/%Y %H:%M'))

    # ── Section 4 : Annotated Image ────────────────────────────────────
    if annotated_path:
        pdf.section_title('4. Image Annotée (Zones Détectées)')
        try:
            img_w = 140
            x_pos = (210 - img_w) / 2
            pdf.image(annotated_path, x=x_pos, w=img_w)
            pdf.ln(4)
        except Exception:
            pass

    # ── Section 5 : Degradations ───────────────────────────────────────
    if analysis.degradations:
        pdf.section_title('5. Dégradations Détectées')
        for d in analysis.degradations:
            conf = float(d.get('confidence', 0))
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(60, 60, 80)
            pdf.cell(55, 7, f"  • {d.get('type', '?').capitalize()} :")
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(0, 7, f"Sévérité {d.get('severity','?')} | Confiance {conf*100:.0f}%")
            pdf.ln()

    # ── Section 6 : Recommendations ───────────────────────────────────
    pdf.section_title('6. Recommandations Techniques')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    for line in rec_text.split('\n'):
        pdf.multi_cell(0, 7, line.strip())
    pdf.ln(2)

    # ── Section 7 : Conclusions ────────────────────────────────────────
    pdf.section_title('7. Conclusions')
    pdf.set_font('Helvetica', '', 10)
    if score >= 70:
        conclusion = (
            'Le bâtiment présente un niveau de dégradation CRITIQUE. '
            'Une intervention immédiate est requise pour prévenir tout risque structurel. '
            'Il est recommandé de consulter un ingénieur structure dans les plus brefs délais.'
        )
    elif score >= 40:
        conclusion = (
            'Le bâtiment présente un niveau de dégradation MODÉRÉ. '
            'Une planification des travaux de restauration à court terme est recommandée. '
            'Un suivi régulier doit être instauré pour surveiller l\'évolution des dégradations.'
        )
    else:
        conclusion = (
            'Le bâtiment est en bon état général. '
            'Les dégradations identifiées sont mineures. '
            'Un entretien préventif annuel est conseillé pour maintenir cet état.'
        )
    pdf.multi_cell(0, 7, conclusion)

    # ── Save ───────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    pdf.output(output_path)
    return output_path
