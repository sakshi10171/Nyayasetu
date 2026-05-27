from groq import Groq
import json
import os
from dotenv import load_dotenv

load_dotenv()
print("API KEY:", os.getenv("GROQ_API_KEY"))

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def extract_action_plan(raw_text):

    prompt = f"""
You are a legal assistant helping Indian government officials understand court judgments.

Read the court judgment text below and extract the following information.

Respond ONLY in valid JSON.
No markdown.
No code blocks.
No explanations.

Required JSON format:

{{
  "case_number": "exact case number from the document",
  "court_name": "name of the court that issued this judgment",
  "judgment_date": "date in DD-MM-YYYY format, or null if not found",
  "parties": "petitioner vs respondent names",
  "judgment_summary": "2-3 sentence plain language summary of what the court decided",
  "directives": [
    "First specific action the government department must take",
    "Second specific action the government department must take"
  ],
  "compliance_deadline": "deadline date in DD-MM-YYYY format, or null if not mentioned",
  "appeal_recommended": false,
  "appeal_reason": ""
}}

Important rules:
- Write directives in simple English.
- Do not use legal jargon.
- Do not invent information.
- If information is missing, use null or empty string.

Judgment text:
{raw_text[:3000]}
"""

    try:
        print("Sending request to Groq...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1
        )

        text = response.choices[0].message.content.strip()
        print("RAW RESPONSE:")
        print(text)

        # Remove markdown formatting safely
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()

        elif text.startswith("```"):
            text = text.replace("```", "").strip()

        # Extract JSON safely
        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end != -1:
            text = text[start:end]

        print("========== GROQ RESPONSE ==========")
        print(text)
        print("===================================")

        data = json.loads(text)

        return {
            "case_number": data.get("case_number", ""),
            "court_name": data.get("court_name", ""),
            "judgment_date": data.get("judgment_date"),
            "parties": data.get("parties", ""),
            "judgment_summary": data.get("judgment_summary", ""),
            "directives": data.get("directives", []),
            "compliance_deadline": data.get("compliance_deadline"),
            "appeal_recommended": data.get("appeal_recommended", False),
            "appeal_reason": data.get("appeal_reason", "")
        }

    except Exception as e:

        print("========== GROQ ERROR ==========")
        print(str(e))
        print("================================")

        return {
            "case_number": "",
            "court_name": "",
            "judgment_date": None,
            "parties": "",
            "judgment_summary": "Extraction failed. Please review manually.",
            "directives": ["Manual review required"],
            "compliance_deadline": None,
            "appeal_recommended": False,
            "appeal_reason": ""
        }