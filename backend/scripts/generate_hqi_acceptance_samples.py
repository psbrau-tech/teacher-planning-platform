# ruff: noqa: E501

from pathlib import Path

from app.document_sections import HqiDocument
from app.document_service import DEFAULT_TEMPLATE_PATH
from app.hqi_document_renderer import render_hqi_document, render_hqi_packet

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "acceptance-output"


def acceptance_payload() -> dict[str, str]:
    return {
        "teacher": "Synthetic Teacher",
        "course": "LET 1",
        "grade": "9-12",
        "week_of": "August 10, 2026",
        "unit_topic": "JROTC Foundations and Leadership Development",
        "standards": "Army JROTC leadership competency and official supporting standards. " * 14,
        "know": "Cadet Creed; chain of command; customs and courtesies; classroom procedures. " * 6,
        "understand": "Individual preparation and disciplined teamwork support unit success. " * 6,
        "do": "Demonstrate customs and courtesies, explain responsibilities, and apply procedures. " * 6,
        "plds": "Level 3: Cadet independently explains expectations and demonstrates procedures. " * 6,
        "misconceptions": "Rank and position are interchangeable; compliance alone equals leadership. " * 5,
        "formative": "Retrieval practice, observation checklist, questioning, and exit ticket. " * 4,
        "summative": "Performance demonstration and short written explanation. " * 4,
        "performance_task": "Lead a small group through a structured classroom procedure. " * 4,
        "resources": "Cadet reference, classroom slides, leadership scenario cards, and rubric. " * 4,
        "clt_mon": "Explain the purpose, structure, and expectations of Army JROTC. " * 9,
        "rrt_mon": "Analyze realistic cadet scenarios and justify the appropriate response. " * 9,
        "cfu_mon": "Use retrieval prompts, cold call, partner explanation, and an exit ticket. " * 8,
        "ri_mon": "Reteach vocabulary and model one scenario before guided practice. " * 8,
        "sic_mon": "Use think time, assigned roles, accountable talk, and precise transitions. " * 8,
        "esl_mon": "Collect scenario responses, observation notes, and exit-ticket evidence. " * 8,
        "reflect_1": "Cadets built knowledge of expectations, terminology, and procedures. " * 12,
        "reflect_2": "Cadets developed an understanding of responsibility and teamwork. " * 12,
        "reflect_3": "Scenario responses and demonstrations provided evidence of learning. " * 12,
        "reflect_4": "Some cadets confused positional authority with effective leadership. " * 10,
        "reflect_5": "Reteach the distinction between compliance, influence, and leadership. " * 10,
        "reflect_6": "Cadets who could not independently explain procedures need intervention. " * 8,
        "reflect_7": "Provide small-group modeling, guided rehearsal, and targeted feedback. " * 8,
        "reflect_8": "Cadets demonstrating early mastery need enrichment opportunities. " * 8,
        "reflect_9": "Assign peer-leadership scenarios and more complex decision tasks. " * 8,
        "reflect_10": "Scenario analysis and structured rehearsal produced strong engagement. " * 8,
        "reflect_11": "Increase retrieval practice and shorten the initial direct instruction. " * 8,
        "reflect_12": "Prioritize procedures, leadership vocabulary, and practical application. " * 8,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = acceptance_payload()

    for document in HqiDocument:
        rendered = render_hqi_document(DEFAULT_TEMPLATE_PATH, payload, document)
        (OUTPUT_DIR / f"{document.value}.pdf").write_bytes(rendered.pdf_bytes)

    packet, _ = render_hqi_packet(DEFAULT_TEMPLATE_PATH, payload)
    (OUTPUT_DIR / "combined-packet.pdf").write_bytes(packet)


if __name__ == "__main__":
    main()
