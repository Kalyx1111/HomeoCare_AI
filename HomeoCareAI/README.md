# HomeoCare AI v1.0
## Homeopathic Medicine Encyclopedia & Case-Taking Platform

## ⚠️ CRITICAL DISCLAIMER
- This is an **educational research tool**, not medical advice, diagnosis, or a prescription
- Mainstream systematic reviews (Australian NHMRC 2015, UK Science & Technology Committee 2010) found **no reliable evidence that homeopathy is effective beyond placebo** for any health condition — this platform states this honestly throughout
- Homeopathy must **never replace vaccination** or evidence-based treatment for serious, chronic, or emergency conditions
- Always consult a **registered homeopathic physician (BHMS, registered with the National Commission for Homoeopathy)** alongside your regular doctor
- **EMERGENCY: Call 112 (India) / 999 (UK) / 911 (US) immediately**

## Quick Start (Windows)
1. Extract ZIP to any folder
2. Double-click **START_HomeoCare_AI.bat**
3. Auto-installs everything (2-5 min first time)
4. Browser opens at **http://localhost:5125**
5. Accept disclaimer and begin

## Flagship Feature — Deep Case-Taking
A genuine 5-step classical homeopathic case interview, far more detailed than a standard symptom checker:
1. **Chief Complaint** — main problem, duration, age, gender
2. **Mental & Emotional Generals** — mood, temperament, fears, causation (grief/shock/fright)
3. **Physical Generals** — thermal reaction (chilly/hot), thirst pattern, food desires/aversions, sleep & dreams, perspiration
4. **Particular Symptoms & Modalities** — exact sensation/location, what aggravates, what ameliorates
5. **History & Causation** — suspected trigger, past/family history

On submission, the AI synthesises a totality-of-symptoms case analysis in classical homeopathic style — 2-4 differentiated remedy suggestions with typical potency conventions, plus detailed **Parhez** (diet & lifestyle guidance) — always followed by the evidence-status disclaimer and a reminder to consult a registered homeopath.

## Reference Library
- **Materia Medica** — 20 major polychrest remedies (Arsenicum Album, Nux Vomica, Pulsatilla, Sulphur, Lycopodium, Sepia, Phosphorus, Belladonna, Rhus Tox, Bryonia, Calcarea Carb, Natrum Mur, Ignatia, Aconite, Apis, Gelsemium, Hepar Sulph, Mercurius, Silicea, Thuja) with full traditional symptom pictures per Boericke's and Kent's classical texts
- **Common Conditions** — 10 common complaints (colds, acidity, headache, joint pain, skin conditions, menstrual complaints, hair fall, allergic rhinitis, piles, anxiety/insomnia), each with traditionally cited remedies **and detailed Parhez**
- **Parhez Guide** — classical antidote-avoidance list, practical dosing habits, general wellness principles
- **Potency & Dosage** — X/D, C, and LM scales explained; classical dosing conventions; safety notes

## Manufacturer Encyclopedia — Researched, Not Hallucinated
Every fact below was verified via web research before writing, per your explicit instruction:
- **SBL** — founded 1983 as Sharda Boiron Laboratories Ltd. (collaboration with Laboratoires Boiron, France); Sahibabad plant near Delhi; today also Jaipur, Haridwar, Sikkim
- **Dr. Willmar Schwabe India** — Indian subsidiary of the German Schwabe Group (founded Leipzig, 1866); incorporated 1994, production from 1997 at its Noida, UP plant
- **Dr. Reckeweg & Co. Germany** — Bensheim-based, founded 1947; famous for numbered **R-series** complex drops (R1–R89+); imported into India via authorised stockists
- **Adel/PEKANA** — PEKANA Naturheilmittel GmbH, Kisslegg, Germany (manufacturing permit 1975); "homeopathic-spagyric" method; distributed in India as Adel India (45+ years)

## Regulatory & Evidence Transparency
Dedicated section covering India's Ministry of AYUSH, the National Commission for Homoeopathy (NCH, successor to the Central Council of Homoeopathy), BHMS qualification requirements — **alongside** an honest summary of the NHMRC (2015) and UK Science & Technology Committee (2010) findings that homeopathy shows no reliable evidence of effect beyond placebo.

## Security — AES-256-GCM + Software Safety Hardening
- API keys AES-256-GCM encrypted client-side before localStorage
- PBKDF2 key derivation (100,000 iterations) from device fingerprint
- XSS protection: escapeHtml(), escapeFilename(), sanitizeAIResponse()
- Backend rate limiting (30 req/60s), input sanitisation/bounding, provider whitelist
- No hardcoded secrets — all API keys from environment or client-supplied at runtime
- AI system prompt explicitly instructs: always disclose evidence status, never suggest vaccination alternatives, always recommend registered-physician consultation

## 6 AI Providers (All Real API Calls)
| Provider | Model | Get Key |
|---|---|---|
| Claude (Anthropic) | claude-sonnet-4-20250514 | console.anthropic.com |
| ChatGPT (OpenAI) | gpt-4o | platform.openai.com/api-keys |
| Gemini (Google) | gemini-2.0-flash | aistudio.google.com/apikey |
| Grok (xAI) | grok-2-latest | console.x.ai |
| DeepSeek | deepseek-chat | platform.deepseek.com/api_keys |
| Mistral AI | mistral-large-latest | console.mistral.ai/api-keys |

## Ambiguity Resolver
Query 2-6 AIs simultaneously — synthesised best answer generated automatically, in the Chat panel.

## Sources
Hahnemann's Organon of Medicine | Boericke's New Manual of Homeopathic Materia Medica | Kent's Materia Medica and Repertory | Ministry of AYUSH | National Commission for Homoeopathy | Official SBL, Schwabe India, Reckeweg, and Adel/Pekana company sources | Australian NHMRC (2015) | UK House of Commons Science and Technology Committee (2010)

*HomeoCare AI — For research and educational purposes only. Not medical advice.*
*Never a substitute for vaccination or emergency care. EMERGENCY: 112 (India) / 999 (UK) / 911 (US)*
