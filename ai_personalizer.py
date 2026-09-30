import os
import re
from google import genai
from google.genai import types

DEFAULT_AI_PROMPT = """You are an expert B2B sales outreach copywriter. Write a concise, genuine, and highly compelling cold outreach message for a brand owner.
Brand Name: {brand}
Store Niche/Products: {niche}
Store Overview/Highlights: {context}
Sender Name: {sender_name}
Sender Company: {company_name}
Goal: Offer custom manufacturing, supply, or B2B collaboration.

Rules:
1. Max 3-4 short sentences (under 60 words).
2. Start with a specific, authentic compliment about their products or brand.
3. Mention that {company_name} can manufacture / supply premium products for their line.
4. End with a friendly, low-pressure call to action (e.g. "Can I send over our mini catalog or samples?").
5. Return ONLY the message text. No subject lines, quotes, or markdown backticks."""

TONE_INSTRUCTIONS = {
    "b2b_wholesale": "Direct, professional B2B wholesale tone. Focus on custom manufacturing, reliable lead times, and low MOQs.",
    "compliment_collab": "Warm, admiring tone. Focus on genuine compliments about their aesthetic/products and a creative partnership opportunity.",
    "cost_margin": "Value-driven business tone. Focus on lowering production costs while improving product finish and margins.",
    "custom": "Follow the user's custom instructions precisely while keeping the message brief and high-converting."
}

def extract_store_context(driver, html=""):
    """
    Extracts concise text highlights (meta description, hero text, about snippet)
    from the current store page to feed into Gemini AI for context.
    """
    context_parts = []
    
    # 1. Meta description
    try:
        meta_desc = driver.find_element("css selector", "meta[name='description']").get_attribute("content")
        if meta_desc and len(meta_desc.strip()) > 10:
            context_parts.append(meta_desc.strip()[:180])
    except:
        pass
        
    # 2. Main H1 headline or hero banner text
    try:
        h1s = driver.find_elements("tag name", "h1")
        for h in h1s[:2]:
            t = h.text.strip()
            if t and len(t) > 5 and len(t) < 80:
                context_parts.append(t)
    except:
        pass

    # 3. Fallback regex on HTML for og:description
    if not context_parts and html:
        m = re.search(r'property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html)
        if m:
            context_parts.append(m.group(1).strip()[:150])

    return " | ".join(context_parts) if context_parts else "Premium online retailer"

def generate_ai_personalized_message(
    brand,
    niche,
    context="",
    sender_name="Our Team",
    company_name="Our Company",
    api_key="",
    tone="b2b_wholesale",
    custom_instructions=""
):
    """
    Calls Google Gemini AI (gemini-2.5-flash) to generate a personalized outreach message.
    Returns (success: bool, message: str).
    """
    key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not key:
        return False, "No Gemini API key provided."

    try:
        client = genai.Client(api_key=key)
        
        tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["b2b_wholesale"])
        if tone == "custom" and custom_instructions:
            tone_instruction = custom_instructions

        prompt = f"""{DEFAULT_AI_PROMPT}

Tone / Strategy:
{tone_instruction}

Information:
- Brand Name: {brand}
- Niche: {niche}
- Context/Details: {context or 'Quality brand products'}
- Sender Name: {sender_name}
- Sender Company: {company_name}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=150,
            )
        )

        text = response.text.strip()
        # Clean any accidental wrapping quotes
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()

        if text and len(text) > 20:
            return True, text
        else:
            return False, "Empty or too short AI response"

    except Exception as e:
        print(f"[Gemini AI Error] {e}")
        return False, str(e)
