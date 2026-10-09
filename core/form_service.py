import json
from pathlib import Path


# File Path
BASE_DIR = Path(__file__).resolve().parent.parent

FORMS_PATH = (
    BASE_DIR
    / "resources"
    / "forms.json"
)

# Load Forms

def load_forms():
    """
    Load all forms from forms.json.
    """

    with open(
        FORMS_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


# Get Form by ID
def get_form_by_id(form_id):
    """
    Find a form by its form ID.
    """

    forms = load_forms()

    for form in forms:
        if form["form_id"] == form_id:
            return form

    return None

# Prepare Forms for DSPy
def get_forms_for_classifier():
    """
    Prepare only the form information needed by DSPy.
    """

    forms = load_forms()

    simplified_forms = []

    for form in forms:
        simplified_forms.append({
            "form_id": form["form_id"],
            "form_name": form["form_name"],
            "description": form["description"]
        })

    return json.dumps(
        simplified_forms,
        ensure_ascii=False,
        indent=2
    )