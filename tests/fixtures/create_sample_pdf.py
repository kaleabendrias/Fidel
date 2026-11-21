"""
Utility to generate a synthetic Ethiopian Grade 12 Physics Unit 2 test PDF.
Contains Roman numeral front matter, Unit 2 headings, physics formulas, and page labels.
Used strictly for unit and integration testing without distributing copyrighted PDFs.
"""

from pathlib import Path
from fpdf import FPDF


def generate_sample_unit2_pdf(output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # Physical Page 0 (PDF Index 0): Cover Page (no printed page label)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 40, "Federal Democratic Republic of Ethiopia", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 20, "PHYSICS", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 14)
    pdf.cell(0, 15, "Student Textbook - Grade 12", ln=True, align="C")
    pdf.cell(0, 15, "2023 New Curriculum", ln=True, align="C")

    # Physical Page 1 (PDF Index 1): Preface (Roman numeral printed page 'iii')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 15, "Preface", ln=True, align="L")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, "This Grade 12 Physics textbook has been designed to meet the requirements of the new Ethiopian general education curriculum framework.")
    # Footer label
    pdf.set_y(270)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 10, "iii", align="C")

    # Physical Page 2 (PDF Index 2): Table of Contents (Roman numeral 'iv')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 15, "Table of Contents", ln=True, align="L")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Unit 1: Application of Physics in Other Fields ........................... 1", ln=True)
    pdf.cell(0, 8, "Unit 2: Two-dimensional Motion ............................................... 34", ln=True)
    pdf.cell(0, 8, "Unit 3: Fluid Mechanics ........................................................... 78", ln=True)
    pdf.set_y(270)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 10, "iv", align="C")

    # Physical Page 3 (PDF Index 3): Unit 2 Title & Overview (Printed page '34')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 15, "Unit 2: Two-dimensional Motion", ln=True, align="L")
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Introduction", ln=True, align="L")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, "In Grade 11, you studied one-dimensional motion along a straight line. In this unit, we extend our kinematics analysis to two dimensions, specifically projectile motion and uniform circular motion.")
    pdf.set_y(270)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "34", align="C")

    # Physical Page 4 (PDF Index 4): Section 2.1 Projectile Motion (Printed page '35')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 12, "2.1 Projectile Motion", ln=True, align="L")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, "Projectile motion is the two-dimensional motion of an object launched into the air, subject only to the acceleration due to gravity g. The horizontal motion has constant velocity vx = v0 * cos(theta), while vertical motion has constant acceleration vy = v0 * sin(theta) - g * t.")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Key Formulas:", ln=True)
    pdf.set_font("Courier", "", 11)
    pdf.multi_cell(0, 6, "Maximum Height: H = (v0^2 * sin^2(theta)) / (2 * g)\nHorizontal Range: R = (v0^2 * sin(2 * theta)) / g\nTime of Flight: T = (2 * v0 * sin(theta)) / g")
    pdf.set_y(270)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "35", align="C")

    # Physical Page 5 (PDF Index 5): Section 2.2 Uniform Circular Motion (Printed page '36')
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 12, "2.2 Uniform Circular Motion", ln=True, align="L")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, "Uniform circular motion describes motion along a circular path at constant speed. Although the speed is constant, the velocity vector continuously changes direction, producing a centripetal acceleration directed toward the center of the circle.")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Centripetal Acceleration Equation:", ln=True)
    pdf.set_font("Courier", "", 11)
    pdf.multi_cell(0, 6, "a_c = v^2 / r = omega^2 * r\nwhere v is tangential speed, omega is angular speed, and r is radius.")
    pdf.set_y(270)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, "36", align="C")

    pdf.output(str(out))
    return out


if __name__ == "__main__":
    target = Path("tests/fixtures/sample_unit2_physics.pdf")
    generate_sample_unit2_pdf(target)
    print(f"Generated sample PDF at: {target}")
