from langgraph.graph import END, StateGraph

from .nodes import check_facts, load_application, prepare_sections, render_pdf, save_resume, tailor
from .state import ResumeState


def build():
    g = StateGraph(ResumeState)
    g.add_node("load_application", load_application.run)
    g.add_node("prepare_sections", prepare_sections.run)
    g.add_node("tailor", tailor.run)
    g.add_node("check_facts", check_facts.run)
    g.add_node("render_pdf", render_pdf.run)
    g.add_node("save_resume", save_resume.run)

    g.set_entry_point("load_application")
    g.add_edge("load_application", "prepare_sections")
    g.add_edge("prepare_sections", "tailor")
    g.add_edge("tailor", "check_facts")
    g.add_edge("check_facts", "render_pdf")
    g.add_edge("render_pdf", "save_resume")
    g.add_edge("save_resume", END)
    return g.compile()
