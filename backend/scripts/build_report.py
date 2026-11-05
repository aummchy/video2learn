"""Generate the new project report (.docx) following the Data Anonymization
report's section structure, with content from the existing Moodle/H5P docx
and the implemented work (local/server Moodle setup, AI + video pipeline).

Formatting mirrors the Data Anonymization PDF from the Table of Contents
page onward: Times New Roman 14 pt body, bold 14 pt headings, centered
section headings, dot-leader TOC, bottom-right page numbers, Letter page.
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_TAB_ALIGNMENT,
    WD_TAB_LEADER,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

OUT = Path("/home/aum/moodle/Developing a Reusable Interactive Learning Platform - Mini Project Report.docx")

FONT = "Times New Roman"

doc = Document()

# ------------------------------------------------------------------ page setup
sec = doc.sections[0]
sec.page_width = Inches(8.5)           # Letter (matches the reference PDF)
sec.page_height = Inches(11)
sec.top_margin = Inches(1.0)
sec.bottom_margin = Inches(0.7)
sec.left_margin = Inches(0.3)          # narrow left edge, as in the source PDF
sec.right_margin = Inches(0.9)
sec.footer_distance = Inches(0.4)
TEXT_WIDTH = 8.5 - 0.3 - 0.9           # 7.3 in — right edge for TOC dot leaders


def _style_font(style, size=14, bold=None):
    """Force Times New Roman on a style and strip theme-font references."""
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        style.font.bold = bold
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "csTheme"):
        key = qn(f"w:{attr}")
        if key in rfonts.attrib:
            del rfonts.attrib[key]
    for attr in ("ascii", "hAnsi", "cs"):
        rfonts.set(qn(f"w:{attr}"), FONT)


# ------------------------------------------------------------ document styles
normal = doc.styles["Normal"]
_style_font(normal, 14)
normal.paragraph_format.line_spacing = 1.15
normal.paragraph_format.space_after = Pt(8)

# section headings — bold 14 pt, black, centered (page breaks kept in body)
h1 = doc.styles["Heading 1"]
_style_font(h1, 14, bold=True)
h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
h1.paragraph_format.space_before = Pt(0)
h1.paragraph_format.space_after = Pt(14)
h1.paragraph_format.keep_with_next = True

# subsection headings — bold 14 pt, black, flush left
h2 = doc.styles["Heading 2"]
_style_font(h2, 14, bold=True)
h2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
h2.paragraph_format.space_before = Pt(16)
h2.paragraph_format.space_after = Pt(4)
h2.paragraph_format.keep_with_next = True

for _name in ("List Bullet", "List Number"):
    _s = doc.styles[_name]
    _style_font(_s, 14)
    _s.paragraph_format.space_after = Pt(6)
    _s.paragraph_format.line_spacing = 1.15

# ------------------------------------------------------------ footer page no.
footer_p = sec.footer.paragraphs[0]
footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
_fr = footer_p.add_run()
_fr.font.name = FONT
_fr.font.size = Pt(10)
_f1 = OxmlElement("w:fldChar")
_f1.set(qn("w:fldCharType"), "begin")
_fi = OxmlElement("w:instrText")
_fi.set(qn("xml:space"), "preserve")
_fi.text = "PAGE"
_f2 = OxmlElement("w:fldChar")
_f2.set(qn("w:fldCharType"), "end")
_fr._r.append(_f1)
_fr._r.append(_fi)
_fr._r.append(_f2)


def h(text, level=1):
    p = doc.add_heading(text, level=level)
    return p


def p(text, bold=False, italic=False):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    return para


def bullets(items, numbered=False):
    style = "List Number" if numbered else "List Bullet"
    for item in items:
        doc.add_paragraph(item, style=style)


def table(headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    for i, head in enumerate(headers):
        t.rows[0].cells[i].text = head
        for r in t.rows[0].cells[i].paragraphs:
            for run in r.runs:
                run.bold = True
    for ri, row in enumerate(rows, start=1):
        for ci, cell in enumerate(row):
            t.rows[ri].cells[ci].text = cell
    for row in t.rows:                     # PDF-like table typography
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(2)
                para.paragraph_format.line_spacing = 1.0
                for run in para.runs:
                    run.font.name = FONT
                    run.font.size = Pt(12)
                    run.font.color.rgb = RGBColor(0, 0, 0)
    doc.add_paragraph()


def box(title, detail=None):
    """One bordered, centered box of the top-down architecture diagram."""
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    t._tbl.tblPr.append(layout)
    t.columns[0].width = Inches(4.9)
    cell = t.rows[0].cells[0]
    cell.width = Inches(4.9)
    first = cell.paragraphs[0]
    first.alignment = WD_ALIGN_PARAGRAPH.CENTER
    first.paragraph_format.space_before = Pt(3)
    first.paragraph_format.space_after = Pt(2 if detail else 4)
    run = first.add_run(title)
    run.bold = True
    run.font.name = FONT
    run.font.size = Pt(14)
    if detail:
        d = cell.add_paragraph()
        d.alignment = WD_ALIGN_PARAGRAPH.CENTER
        d.paragraph_format.space_before = Pt(0)
        d.paragraph_format.space_after = Pt(4)
        dr = d.add_run(detail)
        dr.font.name = FONT
        dr.font.size = Pt(12)
        dr.font.color.rgb = RGBColor(0, 0, 0)
    return t


def arrow():
    """Centered down-arrow between two diagram boxes."""
    a = doc.add_paragraph()
    a.alignment = WD_ALIGN_PARAGRAPH.CENTER
    a.paragraph_format.space_before = Pt(4)
    a.paragraph_format.space_after = Pt(4)
    r = a.add_run("↓")
    r.bold = True
    r.font.size = Pt(16)


# ---------------------------------------------------------------- title page
tp = doc.add_paragraph()
tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = tp.add_run("Walchand College of Engineering, Sangli\n(A Government Aided Institute)\nDepartment of Information Technology")
r.bold = True

tp2 = doc.add_paragraph()
tp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = tp2.add_run("\nMini Project Report\n\nDeveloping a Reusable Interactive Learning Platform for Using Moodle & H5P")
r.bold = True
r.font.size = Pt(16)

doc.add_paragraph()
info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
info.add_run(
    "Submitted by\n\n"
    "Mr. Soham Kanhav  —  246100156\n"
    "Mr. Aum Choudhary  —  246100157\n"
    "Mr. Suyash Shinde  —  246100158\n\n"
    "Project Guide: Prof. D. B. Kulkarni\n"
    "Panel Members: Prof. S. P. Sonavane, Prof. M. G. Rathi\n\n"
    "Academic Year: 2026 - 2027"
)

note = doc.add_paragraph()
note.alignment = WD_ALIGN_PARAGRAPH.CENTER
rn = note.add_run("Note: items in [square brackets] are placeholders — fill them in before submission.")
rn.italic = True

doc.add_page_break()

# ----------------------------------------------------------- table of contents
h("Table of Contents", 1)
toc = [
    (1, "1.  Introduction"),
    (2, "1.1  Overview and Problem Statement"),
    (2, "1.2  Motivation"),
    (2, "1.3  Contributions of this Work"),
    (1, "2.  Project Objectives"),
    (1, "3.  Proposed Method / System"),
    (2, "3.1  Problem Definition"),
    (2, "3.2  Proposed Idea / System"),
    (2, "3.3  System Analysis and Design"),
    (1, "4.  Design and Implementation"),
    (2, "4.1  Requirement Specification"),
    (2, "4.2  Design and Test Steps"),
    (2, "4.3  Moodle AI Integration (Built-in Features)"),
    (1, "5.  Video2Learn — Automated Interactive Video Platform (Detailed)"),
    (2, "5.1  Overview and Purpose"),
    (2, "5.2  System Architecture"),
    (2, "5.3  Pipeline Stages (End to End)"),
    (2, "5.4  H5P Packaging and Moodle Compatibility"),
    (2, "5.5  Design Decisions"),
    (2, "5.6  Validation Results"),
    (1, "6.  Performance Study"),
    (2, "6.1  Implementation Environment"),
    (2, "6.2  Summary of Performance Study"),
    (1, "7.  Conclusions"),
    (1, "8.  References"),
]
for level, text in toc:
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.left_indent = Inches(0.7 if level == 1 else 0.95)
    pf.space_before = Pt(10 if level == 1 else 0)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.15
    pf.tab_stops.add_tab_stop(
        Inches(TEXT_WIDTH), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
    )
    para.add_run(text)
    para.add_run("\t ")

doc.add_page_break()

# ================================================================== 1. Intro
h("1.  Introduction", 1)

p(
    "Digital learning on campus usually involves several disconnected pieces. A teacher "
    "shares a PDF, uploads a recorded lecture, and runs a quiz on another platform, then "
    "tracks marks in a spreadsheet. Students must move between these tools, and teachers "
    "have little visibility into how students are actually learning. The goal of this "
    "project is to change that: to make learning interactive by bringing content, practice "
    "and assessment together on one platform where every activity responds to the student "
    "immediately."
)

h("1.1  Overview and Problem Statement", 2)
p(
    "Traditional learning relies on separate tools — notes or PDFs, recorded video lectures, "
    "stand-alone quizzes and manual progress tracking. Video lectures in particular are "
    "passive: the student watches, but nothing checks whether the concept was understood, "
    "and feedback arrives only later through a separate quiz."
)
p(
    "This project builds a centralized, interactive and reusable learning platform on top of "
    "the open-source Moodle Learning Management System (LMS) and H5P, a toolkit for "
    "interactive HTML5 content. Moodle manages courses, users, assessments and grades, while "
    "H5P turns passive content such as videos into interactive activities with questions and "
    "instant feedback. AI-powered features and an automated video pipeline, added in the "
    "second phase, cut the manual effort of building courses. A reusable Data Structures "
    "course (with Binary Search as the worked example) demonstrates the approach end to end."
)
p(
    "The goal, stated plainly: make learning interactive — every lesson should let the "
    "student act, get feedback and see progress, not just read or watch.",
    bold=True,
)

h("1.2  Motivation", 2)
p(
    "Interactive learning keeps students active: a question inside a video at the moment a "
    "concept is explained forces retrieval practice, and immediate feedback corrects "
    "misunderstandings before they settle. However, building such content by hand is slow — "
    "a teacher must watch the video, decide where to pause, write questions and assemble the "
    "activity. This project is motivated by two needs:"
)
bullets(
    [
        "Give students an interactive experience (video + questions + instant feedback + "
        "grades) inside a single campus-hosted platform.",
        "Reduce the teacher's manual effort through AI tools that summarise text, generate "
        "content, create quizzes and convert plain videos into interactive videos "
        "automatically.",
        "Make the result reusable — the same structured course can be redeployed for every "
        "new batch without being rebuilt.",
    ]
)
p(
    "Two Moodle installations were maintained to support this work: a local development "
    "instance for building and testing features, and a shared server instance that "
    "represents the real campus deployment. Validating on both keeps the platform portable "
    "and version-safe."
)

h("1.3  Contributions of this Work", 2)
p("This project makes three principal contributions:")
p("1.  A clear goal made real — interactive learning on Moodle + H5P.", bold=True)
bullets(
    [
        "Passive materials (PDFs, plain videos) are converted into activities that question, "
        "respond and grade the student at the moment of learning.",
        "Content, practice, assessment and progress tracking live in one place instead of "
        "scattered tools.",
    ]
)
p("2.  What we did — a dual Moodle setup (local and server).", bold=True)
bullets(
    [
        "Local setup: Moodle 5.2.2 installed on Ubuntu Linux with Apache, PHP and MariaDB, "
        "used as the primary development and testing target; H5P verified end-to-end by "
        "building an Interactive Video package, importing it into Moodle and confirming the "
        "video and questions render correctly.",
        "Server setup: the department's shared server running Moodle 4.1.1 as the "
        "production/compatibility target, ensuring exported H5P packages work across both "
        "Moodle version families.",
        "Roles, courses, quizzes, grader report and H5P Content Bank configured on the local "
        "instance with test users.",
    ]
)
p("3.  What we built — AI features and an external-website video pipeline.", bold=True)
bullets(
    [
        "AI Text Summariser — condenses lecture notes into short revision summaries.",
        "AI Text Generator — drafts course explanations and descriptions from a prompt.",
        "AI Quiz Maker — generates practice questions with options and answers.",
        "Automated Interactive Video Pipeline (external website): a separate web "
        "application, Video2Learn, where a teacher uploads a video, AI transcribes it and "
        "places timestamped questions on a review timeline, and a Moodle-compatible H5P "
        "package is produced for import — with no manual H5P authoring.",
    ]
)

doc.add_page_break()

# ================================================================ 2. Objectives
h("2.  Project Objectives", 1)
objectives = [
    "Develop a centralized, Moodle-based learning environment for the Information "
    "Technology department where content, practice and assessment sit together.",
    "Make learning interactive by integrating H5P activities (interactive video, quizzes) "
    "directly into courses, so students receive questions and instant feedback while "
    "studying.",
    "Build a reusable course structure that can be updated and redeployed for future "
    "batches, demonstrated with a Data Structures course.",
    "Set up Moodle locally (development) and on the shared department server "
    "(deployment), and verify that interactive content works on both installations.",
    "Add AI-powered tools — text summariser, text generator and quiz maker — to speed up "
    "content creation and revision.",
    "Automate the conversion of uploaded videos into interactive videos through an "
    "external website, and import the result into Moodle without manual H5P authoring.",
    "Configure suitable teacher, student and administrator workflows with role-based "
    "access.",
    "Evaluate the system through testing and grader-report verification.",
]
for i, obj in enumerate(objectives, 1):
    _para = doc.add_paragraph(f"{i}.  {obj}")
    _para.paragraph_format.space_after = Pt(12)

doc.add_page_break()

# ============================================================ 3. Proposed Method
h("3.  Proposed Method / System", 1)

h("3.1  Problem Definition", 2)
p(
    "Interactive lessons — especially interactive videos — are expensive to produce by "
    "hand, and interactive content must also survive differences between Moodle versions "
    "if it is to be reused. The platform therefore had to solve two problems at once: (a) "
    "give students an interactive learning loop (content → question → immediate feedback → "
    "grade) inside Moodle, and (b) remove the manual effort of creating that content, "
    "while keeping everything compatible with the Moodle installations actually used on "
    "campus (local 5.2.2 and server 4.1.1)."
)

h("3.2  Proposed Idea / System", 2)
p(
    "The system is implemented in three key phases, mirroring how the platform is layered:"
)
p("Phase 1 — Moodle platform (local + server setup)", bold=True)
p(
    "Moodle is installed and configured twice: locally on Ubuntu (Apache, PHP, MariaDB) as "
    "the development instance, and on the shared department server as the deployment "
    "instance. Courses, roles (teacher / student / administrator), quizzes and H5P "
    "activities are configured once and validated on both."
)
p("Phase 2 — H5P interactive layer", bold=True)
p(
    "H5P content (interactive videos, question activities) is created through Moodle's "
    "Content Bank and H5P activities. Interactive content is exported and re-imported as "
    ".h5p packages to prove reusability across courses and across the two Moodle versions."
)
p("Phase 3 — AI automation and the external video website", bold=True)
p(
    "AI tools cut the manual work of Phase 2. Three tools work inside the platform "
    "(summariser, text generator, quiz maker), and a fourth feature — the automated "
    "interactive-video pipeline — runs on an external website separate from Moodle:"
)
bullets(
    [
        "AI Text Summariser: input = long notes or lecture text → output = short key-point "
        "summary for revision.",
        "AI Text Generator: input = topic or prompt → output = draft explanation or "
        "course-unit description for the teacher to edit.",
        "AI Quiz Maker: input = course content or topic → output = practice questions with "
        "options and correct answers, editable before use.",
        "Automated Interactive Video Pipeline (external website, Video2Learn): see the "
        "pipeline below.",
    ]
)

p("Automated Interactive Video Pipeline (detailed)", bold=True)
p(
    "Creating an interactive video normally means watching the whole video, deciding where "
    "to pause, writing questions and building the H5P activity by hand. The pipeline "
    "automates this. The teacher uses an external web application (hosted separately from "
    "Moodle) with three screens — upload, review, export:"
)
bullets(
    [
        "Upload: the teacher uploads an MP4 video, enters a title and selects the language.",
        "Extract audio & transcribe: FFmpeg extracts the audio; a local speech-to-text "
        "engine (Whisper, running on the campus machine — the audio never leaves the "
        "server) produces a timestamped transcript.",
        "AI analysis & question generation: an AI agent reads the timestamped transcript "
        "and generates multiple-choice and true/false questions, each with an explanation "
        "and a suggested timestamp, distributed across the whole video.",
        "Teacher review: a timeline editor shows every question with its timestamp; the "
        "teacher can edit question text, choices, correct answers, explanations and "
        "timing, add or delete questions, and preview the video with the questions "
        "appearing at their timestamps.",
        "H5P export: the app packages the video and questions into a standard .h5p file "
        "(H5P Interactive Video format with MultiChoice and TrueFalse interactions).",
        "Import to Moodle: the teacher uploads the .h5p file into Moodle as an H5P "
        "activity (or into the Content Bank). Moodle downloads the required H5P libraries "
        "automatically on first use.",
        "Student interaction: students watch inside the Moodle course — the video pauses "
        "at each question, the student answers, receives immediate feedback with the "
        "explanation, and Moodle records the attempt and grade.",
    ]
)
p(
    "Pipeline summary:  Video upload (external website) → Speech-to-text → AI question "
    "generation → Teacher review → .h5p package → Import to Moodle → Student interaction "
    "→ Progress & grades",
    bold=True,
)
p(
    "Because the export uses the standard H5P Interactive Video format (not a custom "
    "player), the same package plays on both Moodle installations. Quality check: the "
    "generated questions are a draft — the teacher reviews them on the timeline before the "
    "course goes live."
)

h("3.3  System Analysis and Design", 2)
p(
    "The overall architecture follows the standard Moodle request flow, with the AI "
    "pipeline sitting beside Moodle as an external service:"
)
p(
    "Request flow:  Browser → Apache → Moodle (PHP) → MariaDB (users, courses, grades) "
    "and Moodledata (files, videos, H5P content)"
)
p(
    "Moodle exposes Courses, H5P activities, Quiz, Assignments, Content Bank and the AI "
    "tools to the users. The external video website feeds its .h5p output back into "
    "Moodle through the normal H5P import path, so no Moodle core changes are required."
)
table(
    ["Aspect", "Local Installation", "Server Installation"],
    [
        ["Purpose", "Development and testing", "Shared/production campus use"],
        ["Moodle version", "5.2.2 (Build: 20260810)", "4.1.1"],
        ["Host", "Department machine \"it-it\", Ubuntu 24.04.3 LTS, Intel Core Ultra 5 225H, 30 GB RAM",
         "Department shared server"],
        ["Role", "Primary target for feature work", "Compatibility and deployment target"],
        ["H5P", "Verified: package import renders video + questions",
         "Standard H5P format — portable across installations"],
    ],
)
p("Role-based workflows:")
bullets(
    [
        "Teacher: creates the course, generates content/quizzes with the AI tools, builds "
        "or imports H5P activities, publishes, reviews grader reports.",
        "Student: enrols, studies (AI summaries for revision), interacts with H5P "
        "content, attempts quizzes, receives immediate feedback, sees recorded grades.",
        "Administrator: manages users, roles, plugins, H5P settings and backups.",
    ]
)

doc.add_page_break()

# ============================================ 4. Design and Implementation
h("4.  Design and Implementation", 1)

h("4.1  Requirement Specification", 2)
p("The platform must combine interactivity, reusability and low teacher effort while "
  "running entirely on campus infrastructure. The specific requirements are:")
p("User Requirements:", bold=True)
numbered_user_reqs = [
    "Interactive study loop: students must receive questions and immediate feedback "
    "inside the lesson itself (H5P interactive video and quizzes), not only in separate "
    "quizzes after the fact.",
    "One platform: notes, videos, quizzes, assignments and grades must live in a single "
    "Moodle environment so students and teachers do not switch tools.",
    "Automated content creation: the AI tools must be able to summarise text, generate "
    "course text and create quizzes from teacher-provided input, with the teacher able to "
    "review and edit before publishing.",
    "Video-to-interactive-video automation: a teacher must be able to upload a video to "
    "the external website and receive a Moodle-ready interactive video with minimal manual "
    "work — transcription, question generation and H5P packaging done automatically.",
    "Reusability: courses and H5P content must be exportable and re-importable for future "
    "batches and on both Moodle installations (local 5.2.2 and server 4.1.1).",
    "Role-based access: distinct teacher, student and administrator workflows.",
    "Central progress tracking: quiz attempts, H5P results and course totals must be "
    "collected in Moodle's grader report.",
]
for i, req in enumerate(numbered_user_reqs, 1):
    doc.add_paragraph(f"{i}.  {req}")

p("System Requirements:", bold=True)
table(
    ["Layer", "Technology", "Purpose"],
    [
        ["LMS", "Moodle 5.2.2 (local) / 4.1.1 (server)", "Course and learning management"],
        ["Interactive content", "H5P (Interactive Video, MultiChoice, TrueFalse)", "Interactive learning activities"],
        ["Web server", "Apache 2.4.58 (Ubuntu)", "Serve Moodle"],
        ["Backend", "PHP 8.3.6", "Moodle application logic"],
        ["Database", "MariaDB 10.11", "Users, courses, grades, activities"],
        ["OS", "Ubuntu 24.04 LTS", "Server and deployment environment"],
        ["Video pipeline", "Python 3.12, FastAPI, FFmpeg", "Upload, audio extraction, web app"],
        ["Speech-to-text", "Whisper (faster-whisper, local CPU)", "Timestamped transcript"],
        ["Question generation", "OpenCode CLI (headless AI agent)", "Timestamped quiz questions from transcript"],
        ["AI text tools", "Google Gemini via Moodle's AI subsystem", "Summariser, text generator, quiz maker"],
        ["Frontend", "HTML, CSS, JavaScript", "Moodle UI and pipeline UI"],
    ],
)

h("4.2  Design and Test Steps", 2)
p(
    "We followed a modular approach: stand up Moodle first, prove the interactive layer "
    "manually, then automate content creation on top of a proven path."
)
p("(a) Local Moodle setup", bold=True)
bullets(
    [
        "Installed Ubuntu 24.04 with Apache 2.4.58, PHP 8.3.6 and MariaDB 10.11.",
        "Installed Moodle 5.2.2 at /var/www/moodle with data in /var/moodledata; logged in "
        "as administrator.",
        "Configured an Information Technology course with Announcements, Quiz 1, IT Quiz "
        "and a Peer Evaluation activity; created teacher, student and administrator roles "
        "and test users for the team members.",
        "Enabled and verified H5P: created a test Interactive Video (one video + one "
        "multiple-choice question), exported it as a .h5p package, re-imported it into a "
        "course and confirmed the video plays and the question appears — this validated "
        "the H5P path before any automation was written.",
        "Tested the grader report on the IT Quiz (see Section 6.2).",
    ]
)
p("(b) Server Moodle setup", bold=True)
bullets(
    [
        "Prepared the shared department server running Moodle 4.1.1 as the production/"
        "deployment target.",
        "Used it as the deployment target: the two installations run different Moodle "
        "version families (5.x locally, 4.1.1 on the server), so the tool exports the "
        "standard H5P format that both installations accept.",
    ]
)
p("(c) Feature implementation", bold=True)
bullets(
    [
        "AI Text Summariser, AI Text Generator and AI Quiz Maker: provided through "
        "Moodle's built-in AI subsystem with Google Gemini as the AI provider (see "
        "Section 4.3); output is shown to the teacher for review before it is used in "
        "course activities.",
        "External website — Video2Learn pipeline: FastAPI backend + browser UI with upload, "
        "transcription (FFmpeg + local Whisper), AI question generation (timestamped, "
        "5 multiple-choice + 2 true/false by default for a two-minute video, minimum 15 s "
        "gap), timeline editor with preview, and a standard H5P Interactive Video exporter "
        "(package = h5p.json + content/content.json + video; libraries: InteractiveVideo "
        "1.27, MultiChoice 1.16, TrueFalse 1.8).",
        "H5P exporter kept independent of the AI: the AI produces structured question data; "
        "the exporter converts it to H5P, which allows future support of other H5P library "
        "versions without touching the AI logic.",
    ]
)
p("(d) Test cases", bold=True)
table(
    ["Test case", "Expected result", "Actual result"],
    [
        ["H5P spike package (1 MC + 1 TF) imported into Moodle 5.2.2",
         "Video plays; questions render at their timestamps",
         "PASS — rendered correctly on first import (libraries auto-downloaded from H5P Hub)"],
        ["Full pipeline on a 124.7 s MP4",
         "Transcript + generated questions + valid .h5p",
         "PASS — 24 transcript segments; 7 questions (5 MC + 2 T/F); 8.1 MB package"],
        ["Question editing on the timeline (edit / add / delete, save)",
         "Changes saved and reflected in export",
         "PASS — save round-trip verified; invalid data rejected with an error"],
        ["Exported package structure",
         "Valid ZIP: h5p.json, content.json, video; correct library versions",
         "PASS — structure validated programmatically"],
        ["Grader report on IT Quiz",
         "Scores and course total calculated in one place",
         "PASS — users scored 6.00 and 2.00; average 4.00"],
    ],
)
p("[Insert screenshots: pipeline upload screen, timeline editor with questions, exported "
  ".h5p, video playing with a question inside Moodle, grader report. Replace real email "
  "addresses with test data or hide them.]")

p("(e) Technical issue tackled — H5P video upload failure", bold=True)
p(
    "While exploring the H5P Interactive Video editor, uploading a video failed with the "
    "exception:"
)
p("Exception - finfo_file(): Argument #1 ($finfo) cannot be empty", italic=True)
p(
    "The upload was being rejected because the source file exceeded the size limit applied "
    "to the request. We tackled this by increasing the maximum source size allowed for "
    "video uploads in the Moodle code (raising the video/source limit), after which the "
    "video uploaded successfully and the Interactive Video editor worked normally. This "
    "issue also motivated the design of the Video2Learn exporter (Section 5): because our "
    "tool builds the .h5p package itself, it does not depend on the editor's upload path "
    "at all, so large videos can be packaged and imported without hitting this limit."
)

h("4.3  Moodle AI Integration (Built-in Features)", 2)
p(
    "Beyond H5P, we explored Moodle's built-in AI subsystem — the framework Moodle "
    "provides for connecting external AI providers to educational functionality."
)
p("(i) Understanding Moodle's AI architecture", bold=True)
p("The architecture consists of four concepts:")
bullets(
    [
        "AI Providers: external AI services that provide language models.",
        "AI Placement: defines where AI functionality is available within Moodle.",
        "AI Actions: defines the operations that AI can perform.",
        "AI Tools: functionalities that use AI for specific educational purposes.",
    ],
    numbered=True,
)
p("(ii) Google Gemini integration", bold=True)
p(
    "Google Gemini was configured as an AI provider through Moodle's AI configuration. "
    "The integration was tested using Moodle's available AI functionalities."
)
table(
    ["Parameter", "Configuration"],
    [
        ["AI Provider", "Google Gemini"],
        ["Model", "Gemini 3.5 Flash Lite"],
        ["Tenant", "Default"],
        ["AI Manager", "Moodle AI Manager"],
    ],
)
p("(iii) AI functionalities explored", bold=True)
bullets(
    [
        "Summarise Text — uses the AI model to generate a concise summary of selected text.",
        "Explain Text — uses AI to explain selected text in a more understandable manner.",
        "AI Question Generator — generates assessment questions from supplied text or "
        "course content.",
    ],
    numbered=True,
)
p("(iv) AI question generation and background processing (cron)", bold=True)
p(
    "The built-in AI Question Generator was exercised end to end: open the Question Bank, "
    "start the AI Questions Generator, supply source text, submit the request, and review "
    "the generated questions. Question generation depends on Ad Hoc Tasks that Moodle "
    "processes through cron; Moodle initially showed a notification that cron was not "
    "running, so we executed:"
)
p("sudo -u www-data /usr/bin/php /var/www/moodle/admin/cli/cron.php", italic=True)
p(
    "After cron ran, Moodle processed the pending tasks and two AI-generated questions "
    "appeared in the Question Bank; these were then added to a quiz through the standard "
    "quiz-editing workflow (Add Questions → choose from Question Bank → save), establishing "
    "the path from AI-generated questions to an actual student assessment. Together with "
    "the Gemini provider, this validated Moodle's built-in AI stack — which we contrast "
    "with our own pipeline in Section 5, where questions are generated locally from "
    "video transcripts and delivered inside an interactive video rather than in the "
    "Question Bank."
)

doc.add_page_break()

# ============================== 5. Video2Learn — Automated Interactive Video Platform
h("5.  Video2Learn — Automated Interactive Video Platform (Detailed)", 1)

h("5.1  Overview and Purpose", 2)
p(
    "Video2Learn is a self-hosted web application that turns a plain lecture MP4 into a "
    "Moodle-ready H5P Interactive Video. A teacher uploads a video, the tool transcribes "
    "the speech locally, drafts timestamped questions with AI, lets the teacher review and "
    "edit them on a timeline, and exports a standard .h5p package that can be imported "
    "into any Moodle installation with H5P enabled."
)
p("The design goals were:")
bullets(
    [
        "Make learning interactive: a passive video becomes an assessable lesson — it "
        "pauses at questions, gives immediate feedback and records the attempt.",
        "Keep Moodle untouched: no Moodle plugin is installed; the tool lives outside "
        "Moodle as an external website and produces the standard H5P format, so the same "
        "package imports on the local Moodle 5.2.2 and on the department server's "
        "Moodle 4.1.1.",
        "Keep heavy work out of Moodle: video processing (FFmpeg) and speech recognition "
        "(Whisper) run in Python on the campus machine, not in Moodle's PHP stack.",
        "Keep the teacher in control: the AI drafts, the teacher approves every question "
        "before export.",
        "Protect privacy: audio is transcribed locally, so lecture audio never leaves the "
        "campus machine.",
    ],
)

h("5.2  System Architecture", 2)
p("The architecture of Video2Learn, from top to bottom:")

_architecture = [
    ("Teacher's browser — Video2Learn web UI",
     "upload MP4 · review timeline · preview · download .h5p"),
    ("FastAPI server (localhost:8000)",
     "REST API + in-process background job runner"),
    ("Stage 1 — Upload & validation (media.py)",
     "ffprobe checks MP4 container, H.264 video, AAC audio, resolution, duration"),
    ("Stage 2 — Transcription (transcribe.py)",
     "FFmpeg extracts 16 kHz mono WAV → faster-whisper (base model, CPU int8)"),
    ("Stage 3 — AI question generation (generate.py)",
     "opencode CLI (headless) → validated, timestamped question JSON"),
    ("Stage 4 — Teacher review & export (h5p.py)",
     "edit / preview on the timeline → standard .h5p package"),
    ("Moodle (local 5.2.2 / server 4.1.1)",
     "H5P activity — video pauses at each question, feedback and grades recorded"),
]
for _i, (_title, _detail) in enumerate(_architecture):
    if _i:
        arrow()
    box(_title, _detail)
doc.add_paragraph()          # spacer so the next table is not merged with a box

table(
    ["Component (backend/app)", "Responsibility"],
    [
        ["main.py", "REST API: upload, job status, questions, edit/save, export"],
        ["jobs.py", "Job runner and state machine (uploading → transcribing → "
                    "generating → ready / error), state persisted to disk"],
        ["media.py", "ffprobe validation: MP4 container, H.264 video, audio stream, "
                     "resolution and duration"],
        ["transcribe.py", "FFmpeg extracts 16 kHz mono WAV; faster-whisper (base model, "
                          "CPU int8) produces timestamped segments"],
        ["generate.py", "Builds the AI prompt from the transcript, invokes the opencode "
                        "CLI headless, parses and validates the structured question JSON"],
        ["h5p.py", "Builds the .h5p archive: h5p.json, content/content.json and the "
                   "video; applies H5P semantics defaults"],
        ["frontend (index.html / app.js / style.css)", "Upload, progress, timeline editor, "
                                                       "transcript panel and preview overlay"],
    ],
)
p(
    "Each upload gets its own folder under data/videos/<id>/ holding the original video, "
    "the extracted audio, the transcript, the generated questions and the final package, "
    "so an interrupted job can be resumed and every step is inspectable."
)

h("5.3  Pipeline Stages (End to End)", 2)
table(
    ["Stage", "What happens", "Measured result"],
    [
        ["1. Upload & validation", "MP4 accepted; ffprobe checks codec, resolution, duration",
         "124.7 s, 720p, H.264 + AAC accepted"],
        ["2. Transcription", "FFmpeg → 16 kHz mono WAV → faster-whisper base (CPU int8)",
         "< 10 s → 24 timestamped segments"],
        ["3. AI question generation", "Transcript → prompt → opencode CLI (headless JSON) → "
                                       "validation and normalization",
         "≈ 20–90 s → 7 questions (5 MC + 2 T/F) with explanations"],
        ["4. Teacher review", "Timeline table, edit/add/delete questions, transcript "
                              "click-to-add, live preview overlay, regenerate button",
         "Every question editable; preview pauses the video at its timestamp"],
        ["5. Export", "h5p.py builds the .h5p archive with semantics defaults applied",
         "8.1 MB package; structure validated programmatically"],
        ["6. Moodle import & play", "Upload the .h5p as a course activity; H5P Hub supplies "
                                    "the content-type libraries on first import",
         "Video pauses at each question, feedback shown, attempt recorded"],
    ],
)
p("Question generation rules applied during normalization:", bold=True)
bullets(
    [
        "Question count scales with duration (about one multiple-choice per 25 s of video, "
        "capped at 3–8, plus 1–4 true/false), i.e. 5 MC + 2 T/F for a two-minute video.",
        "Questions are ordered and spread with a minimum 15-second gap so interactions "
        "never overlap.",
        "Timestamps are clamped to the video duration; invalid AI output is rejected and "
        "the request retried (up to 3 attempts).",
        "Each question carries choices, the correct answer and an explanation for feedback.",
    ],
)

h("5.4  H5P Packaging and Moodle Compatibility", 2)
p(
    "The exporter implements the official H5P format directly instead of relying on a "
    "template. A package is a ZIP containing:"
)
bullets(
    [
        "h5p.json — content metadata and the library dependencies: Interactive Video 1.27, "
        "MultiChoice 1.16, TrueFalse 1.8 (versions published by the H5P Hub).",
        "content/content.json — the interactive-video content with the question "
        "interactions at their timestamps (pause enabled on every interaction).",
        "The original video file.",
    ],
)
p(
    "Two compatibility details were validated against the real Moodle installation: the "
    "H5P runtime does not apply semantics defaults itself, so the exporter fills them "
    "(showSolutionButtons, autoPlay, adaptivity, feedback and similar fields); and a few "
    "semantics fields (summary, goto, adaptivity seek) are safely omitted because the "
    "player tolerates their absence. On first import Moodle downloads the content-type "
    "libraries from the H5P Hub once (≈ 30 s); later imports are immediate. Because the "
    "package is standard H5P, the same file can also be imported on the server "
    "Moodle 4.1.1. Packaging outside the H5P editor also sidesteps the "
    "finfo_file upload exception described in Section 4.2(e)."
)

h("5.5  Design Decisions", 2)
bullets(
    [
        "Standard H5P over a custom player: packages work in any Moodle/H5P environment "
        "and survive version differences (5.2.2 vs 4.1.1).",
        "Exporter independent of the AI: the AI only produces structured question data, "
        "so future H5P library versions can be supported without touching generation logic.",
        "Local Whisper instead of a cloud API: speech never leaves the campus machine.",
        "AI drafts, teacher approves: quality control stays with the instructor; a "
        "regenerate button re-runs generation on demand.",
        "Filesystem job store with in-process threads: no external queue or database is "
        "needed for a single-institution tool, and jobs survive restarts.",
        "Plain HTML/CSS/JavaScript frontend: no Node build step, matches the PHP/Moodle "
        "stack the team already operates.",
        "MP4 (H.264 + AAC) only: guaranteed playback in browsers and in the H5P player.",
    ],
)

h("5.6  Validation Results", 2)
p(
    "Beyond the test cases in Section 4.2(d), the pipeline was validated internally: the "
    "AI's JSON output is schema-checked before it reaches the editor; the edit API rejects "
    "invalid payloads (verified with negative tests); every DOM element referenced by the "
    "frontend was cross-checked against the markup; and the exported archive's structure "
    "(files, libraries, content types) was validated programmatically. The full run — "
    "upload to downloadable package — takes about one minute for a two-minute video, "
    "dominated by the teacher's review step, which is by design."
)

doc.add_page_break()

# ======================================================== 6. Performance Study
h("6.  Performance Study", 1)

h("6.1  Implementation Environment", 2)
table(
    ["Component", "Specification"],
    [
        ["Operating system", "Ubuntu 24.04.3 LTS"],
        ["Web server", "Apache 2.4.58 (Ubuntu)"],
        ["PHP", "8.3.6"],
        ["Database", "MariaDB 10.11.14"],
        ["Moodle (local)", "5.2.2 (Build: 20260810)"],
        ["Moodle (server)", "4.1.1"],
        ["H5P content types", "Interactive Video 1.27/1.28, MultiChoice 1.16, TrueFalse 1.8"],
        ["Video pipeline", "Python 3.12, FastAPI, FFmpeg, faster-whisper (base model, CPU int8)"],
        ["Question generation", "OpenCode CLI (headless `opencode run`, JSON output)"],
        ["Development machine", "14-core CPU, 30 GB RAM, no GPU"],
    ],
)

h("6.2  Summary of Performance Study", 2)
p(
    "The pipeline was measured end-to-end on a 124.7-second, 720p MP4 lecture video "
    "(Introduction to FastAPI) on the development machine:"
)
table(
    ["Stage", "Observation"],
    [
        ["Audio extraction (FFmpeg)", "A few seconds for a 125 s video"],
        ["Speech-to-text (Whisper base, CPU)", "Under 10 s → 24 timestamped transcript segments"],
        ["AI question generation", "≈ 20–90 s → 7 questions (5 MC + 2 T/F) with explanations and timestamps"],
        ["Teacher review & export", "Export produced an 8.1 MB .h5p in seconds"],
        ["Total upload → ready", "About one minute for a two-minute video"],
        ["Moodle import", "First import ≈ 30 s (H5P libraries fetched once); later imports immediate"],
        ["Grader report", "Scores 6.00 and 2.00 aggregated correctly; course average 4.00"],
    ],
)
p(
    "Interpretation: transcription runs faster than real time on CPU for short lecture "
    "videos, so the dominant cost is AI question generation (tens of seconds). The overall "
    "time to produce a reviewed, Moodle-ready interactive video is dominated by the "
    "teacher's review step, which is deliberate — the AI drafts, the teacher approves. "
    "Package size is essentially the video size plus a few kilobytes of JSON, so Moodle "
    "upload limits and storage should be considered for long or high-resolution videos."
)

doc.add_page_break()

# =============================================================== 7. Conclusions
h("7.  Conclusions", 1)
p(
    "This project set out with a single goal — to make learning interactive — and "
    "delivered it as a reusable platform built on existing campus infrastructure. Moodle "
    "manages the learning environment and H5P provides the interactive layer: videos "
    "pause for questions, students receive immediate feedback, and every attempt is "
    "recorded centrally in the grader report."
)
p(
    "In terms of what we did, Moodle was set up locally (5.2.2 on Ubuntu with Apache, PHP "
    "and MariaDB) as the development and verification instance, and on the shared department "
    "server (4.1.1) as the deployment target. The H5P path was validated end to end — a "
    "generated Interactive Video package was imported and rendered correctly — giving "
    "confidence that content is portable across both installations."
)
p(
    "In terms of features, three AI tools (text summariser, text generator, quiz maker) "
    "running on Moodle's built-in AI subsystem with Google Gemini reduce the effort of "
    "building courses and speed up revision, and the automated "
    "interactive-video pipeline on the external website removes the most repetitive task "
    "of all: a plain MP4 becomes a timestamped, question-annotated, Moodle-ready H5P "
    "activity in about a minute, with the teacher remaining in control through the review "
    "timeline. Together with the reusable Data Structures course structure (Binary Search "
    "as the worked example), the platform demonstrates that the same course can be "
    "updated and redeployed for future batches."
)

# ================================================================ 8. References
doc.add_page_break()
h("8.  References", 1)
refs = [
    "Moodle Official Documentation — https://docs.moodle.org",
    "H5P Official Documentation — https://h5p.org/documentation",
    "H5P Interactive Video content type — https://h5p.com/content-types/interactive-video",
    "Moodle H5P documentation (4.1 / 5.x) — https://docs.moodle.org/401/en/H5P",
    "Moodle Plugin Directory — https://moodle.org/plugins",
    "PHP Documentation — https://www.php.net/docs.php",
    "MariaDB Documentation — https://mariadb.com/kb/en/documentation/",
    "Apache HTTP Server Documentation — https://httpd.apache.org/docs/",
    "FFmpeg Documentation — https://ffmpeg.org/documentation.html",
    "Whisper / faster-whisper — speech-to-text engine used in the video pipeline",
    "FastAPI Documentation — https://fastapi.tiangolo.com",
    "Moodle AI subsystem documentation — https://docs.moodle.org",
    "Google Gemini API — https://ai.google.dev (AI provider used with Moodle)",
    "OpenCode CLI — https://opencode.ai (headless question generation in Video2Learn)",
    "Video2Learn — the external video-to-interactive-video website built in this "
    "project (self-hosted)",
]
for i, ref in enumerate(refs, 1):
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.left_indent = Inches(0.3)
    pf.first_line_indent = Inches(-0.3)
    pf.space_after = Pt(16)
    pf.line_spacing = 1.15
    para.add_run(f"[{i}]  {ref}")

doc.save(OUT)
print(f"wrote {OUT}")
