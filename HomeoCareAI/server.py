"""
HomeoCare AI - Production Backend Server v1.0
Homeopathic Medicine Encyclopedia & Case-Taking Research Platform
Port: 5125
=========================================
DISCLAIMER: All AI output is for research/education only, describing
homeopathy as a system of medicine per its own classical literature
and as regulated in India by the Ministry of AYUSH / National
Commission for Homoeopathy (NCH). This is NOT medical advice, NOT a
prescription, and NOT a substitute for consulting a registered
homeopathic physician (BHMS/registered with NCH) or a conventional
doctor. Homeopathy must never replace evidence-based treatment,
vaccination, or emergency care for serious, chronic, or
life-threatening conditions. EMERGENCY: Call 112 (India) / 999 (UK)
/ 911 (US) immediately.
"""

import os, sys, json, uuid, time, hashlib, logging, datetime, argparse
from pathlib import Path

try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("[FATAL] Flask not installed. Run REPAIR_AND_RECOVER.bat"); sys.exit(1)

try:
    import requests as req_lib; REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import fitz; FITZ_OK = True
except ImportError:
    FITZ_OK = False

try:
    from PIL import Image; PIL_OK = True
except ImportError:
    PIL_OK = False

sys.path.insert(0, str(Path(__file__).parent / "modules"))
try:
    import ai_providers; AI_PROVIDERS_OK = True
except ImportError:
    AI_PROVIDERS_OK = False

BASE_DIR    = Path(__file__).parent.resolve()
UPLOAD_DIR  = BASE_DIR / "uploads"
LOGS_DIR    = BASE_DIR / "logs"
DATA_DIR    = BASE_DIR / "data"
STATIC_DIR  = BASE_DIR / "static"
REPORTS_DIR = BASE_DIR / "reports_db"

for d in [UPLOAD_DIR, LOGS_DIR, DATA_DIR, STATIC_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── SOFTWARESAFETY: no hardcoded secrets — all keys from env or client-supplied at runtime ──
PORT    = int(os.environ.get("HOMEOCARE_PORT", 5125))
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_PROVIDER_KEYS = ai_providers.get_env_keys() if AI_PROVIDERS_OK else {}
VERSION = "1.0.0"

DISCLAIMER = (
    "WARNING - AI RESEARCH DISCLAIMER: HomeoCare AI describes homeopathy as a "
    "system of medicine, per classical homeopathic literature (Hahnemann's Organon, "
    "Boericke's and Kent's Materia Medica) and as regulated in India by the Ministry "
    "of AYUSH / National Commission for Homoeopathy (NCH, formerly Central Council "
    "of Homoeopathy). This is educational information only - NOT medical advice, "
    "NOT a diagnosis, and NOT a prescription. Mainstream systematic reviews (the "
    "Australian NHMRC 2015 review, the UK House of Commons Science and Technology "
    "Committee 2010) found no reliable evidence that homeopathy is effective beyond "
    "placebo for any health condition. Homeopathy should NEVER replace vaccination "
    "or evidence-based treatment for conditions that are serious, chronic, or could "
    "become serious, or in any emergency. ALWAYS consult a qualified, registered "
    "homeopathic physician (BHMS, registered with NCH) alongside your regular "
    "doctor before starting any remedy, and never stop or delay conventional "
    "treatment without your doctor's advice. EMERGENCY: Call 112 (India) / 999 "
    "(UK) / 911 (US) immediately."
)

log_file = LOGS_DIR / f"server_{datetime.date.today()}.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("HomeoCareAI")

app = Flask(__name__, static_folder=str(STATIC_DIR))
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
CORS(app, origins="*")  # local single-user tool; no auth/session/cookie state to protect

_RATE_STORE = {}

def _get_client_id():
    return hashlib.sha256((request.remote_addr or "127.0.0.1").encode()).hexdigest()[:16]

def rate_limit_check():
    """SOFTWARESAFETY: route throttling on all endpoints."""
    cid = _get_client_id(); now = time.time()
    _RATE_STORE.setdefault(cid, [])
    _RATE_STORE[cid] = [t for t in _RATE_STORE[cid] if now - t < 60]
    if len(_RATE_STORE[cid]) >= 30: return False
    _RATE_STORE[cid].append(now); return True

def sanitise_api_key(key):
    """SOFTWARESAFETY: treat all client input as untrusted — validate and strip."""
    if not key or not isinstance(key, str): return ""
    key = key.strip()
    if len(key) > 512: return ""
    s = "".join(c for c in key if 0x21 <= ord(c) <= 0x7E)
    return s if len(s) >= 10 else ""

def validate_provider(p):
    """SOFTWARESAFETY: whitelist validation — reject anything not in the known set."""
    valid = {"anthropic","openai","gemini","grok","deepseek","mistral"}
    return p.lower() if p and p.lower() in valid else "anthropic"

def sanitise_text_field(val, max_len=500):
    """SOFTWARESAFETY: bound and strip all free-text client input before use in prompts/logs."""
    if not val or not isinstance(val, str): return ""
    return val.strip()[:max_len]

# ═══════════════════════════════════════════════════════════════
# HOMEOPATHY KNOWLEDGE BASE
# Sources: Hahnemann's Organon of Medicine; Boericke's New Manual
#          of Homeopathic Materia Medica; Kent's Materia Medica and
#          Repertory; Ministry of AYUSH / National Commission for
#          Homoeopathy (NCH); official company sources for SBL,
#          Dr. Willmar Schwabe India, Dr. Reckeweg & Co. Germany,
#          and ADEL/PEKANA; Australian NHMRC (2015) and UK House of
#          Commons Science & Technology Committee (2010) for
#          evidence status.
# ═══════════════════════════════════════════════════════════════
KNOWLEDGE = {
    "principles_of_homeopathy": {
        "name": "Principles of Homeopathy",
        "founder_and_history": "Homeopathy was developed by the German physician Dr. Christian Friedrich Samuel Hahnemann (1755-1843), born in Meissen, Germany. Dissatisfied with the harsh medical practices of his era (bloodletting, purging), Hahnemann began self-experimentation in 1790 with cinchona bark, observing that it produced fever-like symptoms in himself as a healthy person similar to the malaria symptoms it was used to treat. This led him to formulate the principle of 'similia similibus curentur' (let likes be cured by likes) around 1796. He compiled his complete system in the 'Organon of Medicine', first published in 1810 and revised through six editions during his lifetime (final 6th edition published posthumously). World Homeopathy Day is observed annually on 10 April, marking Hahnemann's birth anniversary.",
        "law_of_similars": "The central principle: a substance capable of producing a specific set of symptoms in a healthy person (established through 'provings' - systematic testing of substances on healthy volunteers with careful documentation) can, in a highly diluted form, be used to treat a sick person presenting with a similar symptom picture. This is the founding logic of remedy selection in classical homeopathy.",
        "minimum_dose_and_potentization": "Hahnemann proposed that remedies should be given in the smallest possible dose to minimise adverse effects, using a process he called 'potentization' - serial dilution combined with vigorous shaking ('succussion') at each stage. Dilution scales in classical use: the decimal (X or D) scale, each step diluting 1:10; the centesimal (C) scale, each step diluting 1:100; and the LM (or Q) potency scale, a very high dilution introduced by Hahnemann in his final years, using a different succussion method. Homeopaths hold that this process increases a remedy's therapeutic action while reducing material toxicity - a claim not supported by conventional pharmacology or physical chemistry, since many potencies exceed the point at which any molecule of the original substance is statistically likely to remain (a fact widely discussed in the scientific literature on homeopathy).",
        "individualisation_and_totality": "Classical homeopathy emphasises treating the whole person rather than a named disease label, based on the 'totality of symptoms' - the complete, individualised pattern of a person's mental state, general physical characteristics, and particular local complaints. Two people with the same diagnosed condition may, in classical homeopathic practice, be prescribed different remedies if their overall symptom pictures differ. This individualisation is why homeopathic case-taking interviews are typically much longer and more detailed than a standard clinical consultation.",
        "single_remedy_and_provings": "Classical (Hahnemannian) homeopathy generally favours prescribing one remedy at a time, at one potency, then observing the response before making any change - in contrast to some modern 'complex' or combination remedies (blends of several homeopathic substances marketed for a specific named condition, common among brands such as Dr. Reckeweg's R-series and SBL's combination products) which depart from this classical single-remedy approach. A 'proving' (German: Arzneimittelprüfung) is the systematic process of administering a substance to healthy volunteers and recording all symptoms produced, forming the basis of each remedy's documented 'symptom picture' in the materia medica.",
    },
    "case_taking_methodology": {
        "name": "Homeopathic Case-Taking Methodology",
        "overview": "Homeopathic case-taking is traditionally far more extensive than a conventional medical history, because remedy selection depends on the complete individual picture rather than a diagnostic label alone. A classical first consultation can take 45-90 minutes or longer. The case is generally structured into mental/emotional generals, physical generals, particular (local) symptoms, and modalities, before arriving at a shortlist of indicated remedies through a process called repertorisation (cross-referencing symptoms against a repertory - an indexed reference of symptoms and the remedies associated with each).",
        "mental_emotional_generals": "Questions explore the person's emotional temperament and its recent changes: predominant mood (irritable, weepy, anxious, indifferent), reaction to consolation or sympathy (desires it vs. is averse to it), specific fears (of death, of the dark, of being alone, of heights, of failure), memory and concentration, reaction to disappointment or grief, sleep-related mental state, and any recent emotional triggers (grief, humiliation, fright, disappointment) that preceded the onset of physical symptoms - homeopaths consider such causation highly significant in remedy selection.",
        "physical_generals": "These describe how the whole body behaves, independent of the presenting complaint, and are considered highly weighted in classical case analysis: thermal reaction (whether the person generally feels the cold more than others, or the heat more - 'chilly' vs. 'hot' patient), thirst (quantity and frequency - thirstless, or thirsty for small frequent sips, or large infrequent quantities), specific food desires and aversions (cravings for salt, sweets, sour foods, or aversions to specific foods), quality and position of sleep, characteristic dreams, perspiration (location, odour, and whether it relieves or does not relieve symptoms), and general reaction to weather, seasons, or time of day.",
        "particular_symptoms_and_modalities": "The specific presenting complaint is explored in fine detail: exact location, sensation (burning, stitching, throbbing, cramping - the precise quality matters a great deal in homeopathic differentiation), radiation, and severity. Modalities - factors that make a symptom clearly better or worse - are considered essential: aggravation or amelioration from motion versus rest, warmth versus cold, pressure, position, time of day, weather, eating, or specific activities. Two remedies with an apparently similar symptom picture are frequently distinguished from each other almost entirely on the basis of their opposite modalities (for example, Rhus Toxicodendron is characteristically worse on first movement and better with continued motion, while Bryonia is characteristically worse from any motion and better for absolute rest).",
        "history_and_causation": "Family history (particularly of chronic conditions, which classical homeopathy groups under inherited tendencies called 'miasms'), past illnesses and their treatment, obstetric/menstrual history where relevant, and the identified or suspected causation of the current complaint (exposure to cold/damp, grief, fright, overwork, dietary indiscretion) are all recorded as part of a complete case.",
    },
    "materia_medica_polychrests": {
        "name": "Materia Medica - Major Polychrest Remedies",
        "note": "The following are among the most extensively used 'polychrest' (broad-application) remedies in classical homeopathic materia medica (per Boericke's New Manual of Homeopathic Materia Medica and Kent's Lectures). Each entry describes the traditional symptom picture used for remedy selection; it is not a claim of proven clinical efficacy.",
        "arsenicum_album": "Source: white arsenic (Arsenic trioxide), used at homeopathic dilution. Traditional picture: anxious, restless, meticulously tidy/fastidious, fear of death and of being left alone, marked exhaustion out of proportion to exertion. Physical generals: markedly chilly, better for warmth; thirsty for small sips at frequent intervals; burning pains that are, characteristically, better for warmth (an apparent paradox often cited to distinguish it). Particular: classic picture of acute gastroenteritis with simultaneous vomiting and diarrhoea, both worse after eating or drinking, and marked prostration; also used in the classical literature for allergic rhinitis and anxious restlessness. Typically used at 6C-30C for acute presentations in classical practice.",
        "nux_vomica": "Source: seeds of Strychnos nux-vomica. Traditional picture: irritable, impatient, competitive, oversensitive to noise/light/odours, a 'driven' constitution associated with overwork and overindulgence (rich food, alcohol, coffee, tobacco, sedentary habits). Physical generals: chilly, worse in the morning on waking. Particular: classic remedy in the traditional literature for digestive upset from dietary or lifestyle excess, constipation with frequent ineffectual urging, and irritability associated with modern high-stress lifestyles.",
        "pulsatilla": "Source: Pulsatilla nigricans (pasque flower/windflower). Traditional picture: gentle, tearful, seeks company and consolation, changeable mood and changeable physical symptoms. Physical generals: warm-blooded (better in open air, worse in warm closed rooms), characteristically thirstless even with fever. Particular: traditionally indicated for colds/catarrh with thick, bland, yellow-green discharge, and for menstrual complaints with a variable, changeable pattern.",
        "sulphur": "Source: elemental sulphur. Traditional picture: intellectually curious, philosophical, often untidy or unconcerned about personal appearance. Physical generals: hot-blooded (dislikes heat, better in open air), burning sensations especially of the soles of the feet (classically described as pushing the feet out from under the bedcovers at night), hungry/sinking sensation around 11am. Regarded in classical practice as a deep-acting 'constitutional' remedy, often used for chronic skin conditions and as an intercurrent remedy when treatment seems to stall.",
        "lycopodium": "Source: spores of the club moss Lycopodium clavatum. Traditional picture: outward confidence masking inner self-doubt, fear of failure/responsibility, irritability especially on first waking, dislike of company yet dislike of being entirely alone. Physical generals: symptoms classically worse between 4pm-8pm; craves sweets. Particular: bloating and fullness after eating, especially worse with beans, cabbage, and other gas-forming foods; right-sided complaints or symptoms moving from right to left are traditionally noted as suggestive.",
        "sepia": "Source: ink of the cuttlefish (Sepia officinalis). Traditional picture: emotional exhaustion, irritability, indifference towards loved ones and activities usually enjoyed, yet aversion to sympathy/consolation (a distinguishing point from Pulsatilla). Physical generals: chilly, marked improvement from vigorous exercise, craves sour foods/vinegar. Particular: traditionally associated with a bearing-down/sagging sensation, and used in the classical literature for complaints around menopause, postpartum exhaustion, and hormonal-pattern complaints.",
        "phosphorus": "Source: elemental phosphorus. Traditional picture: sociable, sympathetic, imaginative, craves reassurance and company, marked fears (thunderstorms, twilight, being alone). Physical generals: often a tall, slim build; craves cold drinks, ice cream, salty food; bleeds easily (traditionally described as a 'haemorrhagic' tendency); burning pains better for cold applications (contrast with Arsenicum). Particular: used in the classical literature for respiratory complaints and for a generally sensitive, easily-startled constitution.",
        "belladonna": "Source: deadly nightshade (Atropa belladonna). Traditional picture: an acute remedy for sudden, violent onset - high fever with a hot, flushed, red face, throbbing sensation, dilated pupils, dry radiating heat without proportionate thirst. Modalities: worse from light, noise, jarring movement, and touch; better sitting semi-upright. Classic traditional indication: sudden high fever and throbbing headache of rapid onset.",
        "rhus_toxicodendron": "Source: poison ivy (Toxicodendron radicans/pubescens). Traditional picture and hallmark modality: worse on first beginning to move after rest ('rusty gate' stiffness), but better with continued gentle motion; worse from cold and damp, better from warmth. Particular: joint and muscular stiffness/pain, restlessness (constant desire to change position for relief). One of the most frequently cited remedies in the traditional literature for musculoskeletal stiffness and sprains.",
        "bryonia_alba": "Source: white bryony root. Traditional picture and hallmark modality: worse from any motion at all, even slight; markedly better for absolute rest, firm pressure, and lying on the painful side - the direct modality contrast to Rhus Toxicodendron. Marked thirst for large quantities of water at long intervals. Particular: traditionally used for dry, painful cough worse on movement/deep breathing, and for joint pain aggravated by any motion.",
        "calcarea_carbonica": "Source: calcium carbonate, from the middle layer of the oyster shell. Traditional picture: cautious, methodical, easily overwhelmed by responsibility, obstinate; in children, associated with slower physical development. Physical generals: chilly, tends towards a soft/flabby build, characteristic profuse sweating of the head during sleep (particularly noted in children), craves eggs, worse from cold/damp and from exertion.",
        "natrum_muriaticum": "Source: sodium chloride (common salt). Traditional picture: reserved, internalises grief and old emotional hurts, dislikes and is worse from consolation or fuss (a distinguishing feature from Pulsatilla), tends to weep in private rather than in company. Physical generals: strong salt craving, marked thirst, symptoms often worse from sun exposure or heat. Particular: traditionally used for recurring/periodic headaches associated with sun exposure and for cold sores.",
        "ignatia_amara": "Source: St. Ignatius bean (Strychnos ignatii). Traditional picture: the principal traditional remedy for acute grief or emotional shock, marked by paradoxical or rapidly alternating symptoms (sighing, alternating laughter and tears), a characteristic 'lump in the throat' sensation (globus), and symptoms that are, unusually, worse rather than better for consolation.",
        "aconitum_napellus": "Source: monkshood (Aconitum napellus). Traditional picture: sudden onset, often following exposure to cold dry wind or a fright/shock, with intense anxiety, restlessness, and a characteristic fear of death with a sense of knowing the exact time. Traditionally reserved in the classical literature for the very earliest stage of an acute illness, before more specific/localised symptoms develop.",
        "apis_mellifica": "Source: whole honeybee, prepared at homeopathic dilution. Traditional picture: stinging, burning pains with marked oedematous swelling, better for cold applications, worse for heat, touch, and pressure; notably thirstless even with fever. Traditionally associated in the literature with rapid-onset allergic swelling and insect-sting-type reactions.",
        "gelsemium_sempervirens": "Source: yellow jasmine root. Traditional picture: anticipatory anxiety (e.g., before an examination or public performance), profound weakness, heaviness, trembling, and drowsy, drooping eyelids. Particular: traditionally used for influenza-type illness with chills running up and down the spine, dull heavy headache, and a notable absence of thirst despite fever.",
        "hepar_sulphuris_calcareum": "Source: calcium sulphide, prepared by heating oyster shell with sulphur. Traditional picture: extreme sensitivity to pain, cold air, and touch; irritable; a marked tendency in the traditional literature towards suppuration (abscess/pus formation) once infection is established. Characteristic splinter-like, sharp local pain. Better for warmth and wrapping up; worse for cold, even a draught.",
        "mercurius_solubilis": "Source: a soluble mercury compound, prepared at homeopathic dilution. Traditional picture: excessive salivation, offensive breath and perspiration (without corresponding relief), swollen glands, and marked sensitivity to both heat and cold. Traditionally used in the literature for throat and glandular infections with these accompanying features.",
        "silicea": "Source: pure flint/silicic acid. Traditional picture: a thin, chilly constitution with poor physical stamina but stubborn determination and conscientiousness over small details. Physical generals: profuse, offensive sweating of the feet; brittle nails and hair. Particular: traditionally associated with a tendency to suppuration and with the body 'expelling' foreign material (splinters), better for warmth and for wrapping the head.",
        "thuja_occidentalis": "Source: white cedar/arbor vitae. Traditional picture: fixed ideas, fastidiousness, a characteristic sensation of fragility (as if made of glass or as if a limb were not one's own). Particular: the principal traditional remedy associated with warts and other skin growths in the classical literature, worse from dampness.",
    },
    "potency_dosage_administration": {
        "name": "Potency, Dosage & Administration Conventions",
        "potency_scales": "Three dilution/potency scales are used in classical practice: the decimal (X/D) scale, diluting 1 part in 10 at each stage; the centesimal (C) scale, diluting 1 part in 100 at each stage (30C means the process was repeated 30 times); and the LM (or Q) scale, an even higher dilution introduced by Hahnemann late in his life, prepared and succussed differently from the C scale. Common potencies encountered in Indian retail homeopathic products include 6C, 30C, 200C, 1M (1000C) and 10M, as well as 3X, 6X, 12X and 30X on the decimal scale, and mother tinctures (undiluted or minimally processed source extract, denoted 'Q' or 'MT') used both internally (per label/practitioner instruction) and topically.",
        "classical_dosing_conventions": "In common Indian retail and classical teaching practice: lower potencies (6C/30C, or the X scale) are often associated with more physical/local, acute complaints and are conventionally taken more frequently (e.g., a few times a day during an acute episode); higher potencies (200C and above) are conventionally associated with more constitutional prescribing and taken less frequently (occasionally a single dose, followed by a waiting period to observe the response). These are general conventions described in classical texts and on manufacturer packaging, not fixed rules, and actual prescribing decisions (remedy, potency, and repetition) are the responsibility of a qualified homeopathic physician based on the individual case.",
        "administration_technique": "Classical and manufacturer guidance commonly advises: take remedies on a clean tongue, ideally away from food, drink, tobacco, or strong flavours (allow a gap of about 15-30 minutes before and after eating, drinking, or brushing teeth); avoid directly touching pellets/globules with the hand (tip into the cap or a spoon first) to avoid contaminating the remaining dose; store bottles tightly closed, away from direct sunlight, strong heat, and strong-smelling substances (camphor, perfumes, mothballs) which are traditionally believed by homeopaths to affect the remedy's potency, though this claim has not been independently, scientifically established.",
        "safety_note": "Homeopathic remedies at high dilutions (12C and beyond) are generally regarded as containing negligible or no molecules of the original substance and are widely considered to carry very low risk of direct pharmacological/toxic effect - however, mother tinctures and low potencies (which retain more of the original material) should be used strictly as labelled or as directed by a registered practitioner. Some 'complex'/combination products contain multiple ingredients at varying potencies and should also be used only as labelled or prescribed. As with any product, discontinue and seek medical advice if any unexpected reaction occurs.",
    },
    "common_conditions_remedies": {
        "name": "Common Conditions - Traditional Remedy Reference",
        "note": "This section reflects commonly cited remedy options per classical homeopathic and manufacturer literature for minor, self-limiting complaints, alongside general dietary guidance ('Parhez'). It is not a substitute for individualised prescribing by a registered homeopath, and is not appropriate for serious, chronic, worsening, or emergency conditions, which require conventional medical evaluation.",
        "common_cold_coryza": "Traditionally cited options include Allium Cepa (watery eyes and profuse burning nasal discharge, classic 'onion' picture), Pulsatilla (thick bland yellow-green discharge, better in open air), Arsenicum Album (thin burning discharge with restlessness), Nux Vomica (blocked nose at night, runny by day, from cold dry wind exposure), Kali Bichromicum (thick stringy/ropy discharge with sinus pressure). Parhez: warm fluids, avoid cold drinks/ice cream and cold exposure, steam inhalation, avoid dairy in excess for some individuals if it appears to increase mucus, adequate rest.",
        "acidity_hyperacidity_gastritis": "Traditionally cited options include Nux Vomica (from dietary/lifestyle excess, worse morning), Carbo Vegetabilis (marked bloating, sluggish digestion, better from belching), Robinia (pronounced acid regurgitation), Arsenicum Album (burning pain better for warm food/drink). Parhez: avoid fried, spicy, and oily food; limit tea/coffee/carbonated drinks and alcohol; eat smaller, more frequent meals rather than large ones; avoid lying down immediately after eating; reduce late-night eating.",
        "headache_migraine": "Traditionally cited options include Belladonna (sudden throbbing headache with flushed face, worse light/noise), Natrum Muriaticum (periodic headache associated with sun exposure, often with visual disturbance beforehand), Bryonia (bursting headache worse for any movement, better for firm pressure and lying still), Nux Vomica (headache after overindulgence in food/alcohol or from overwork), Gelsemium (dull band-like headache with heaviness of the eyelids). Parhez: identify and avoid personal dietary triggers where relevant (common ones cited include caffeine withdrawal, aged cheese, chocolate, alcohol), maintain regular meal and sleep timing, adequate hydration, limit prolonged screen exposure.",
        "joint_pain_arthritis": "Traditionally cited options include Rhus Toxicodendron (stiffness worse on first movement, better with continued gentle motion, worse cold/damp), Bryonia (pain worse from any movement, better for rest and pressure), Calcarea Carbonica (in a chilly, flabby constitution), Ledum Palustre (traditionally for joint pain that ascends from the lower to upper body). Parhez: maintain a healthy body weight to reduce joint load, gentle regular movement/physiotherapy as advised by a doctor, warm applications for Rhus tox-type stiffness, adequate calcium/vitamin D-rich foods, limit excess purine-rich foods (organ meats, certain seafood) if a gout-type picture has been diagnosed by a physician.",
        "skin_conditions_eczema_acne": "Traditionally cited options include Sulphur (chronic itching worse from heat/bathing, in an otherwise generally healthy-appearing individual), Graphites (skin that oozes a honey-like discharge, tends to crack, in a chilly/overweight constitution), Rhus Toxicodendron (intensely itchy vesicular eruptions), Hepar Sulphuris (skin lesions with a tendency to suppurate, extremely sensitive to touch), Antimonium Crudum (acne with a thickly coated white tongue, worse from overheating). Parhez: limit high-sugar and highly processed food, maintain good hydration, gentle non-irritating skincare, avoid excessive sun exposure without protection, avoid squeezing/picking lesions.",
        "menstrual_complaints": "Traditionally cited options include Pulsatilla (changeable, variable menstrual pattern, better emotional support and open air), Sepia (bearing-down sensation, irritability, marked fatigue), Magnesia Phosphorica (cramping pain relieved by warmth and firm pressure), Cimicifuga (cramping pain with marked mood changes premenstrually), Sabina (heavy bleeding with clots). Parhez: warm applications for cramping, adequate iron-rich food if heavy flow (with medical monitoring of haemoglobin), regular gentle exercise, adequate rest during menses, limit excess caffeine premenstrually if it appears to worsen symptoms for the individual.",
        "hair_fall": "Traditionally cited options include Phosphorus (diffuse hair fall, especially after illness or emotional stress), Silicea (weak, brittle hair and nails, generally low physical stamina), Natrum Muriaticum (hair fall associated with grief or emotional strain), Lycopodium (early greying/thinning with digestive complaints). Parhez: adequate dietary protein, iron, and biotin-rich foods, gentle hair handling (avoid harsh chemical treatments/excess heat styling), address any underlying thyroid or nutritional cause identified through conventional blood tests, manage stress.",
        "allergic_rhinitis_sinusitis": "Traditionally cited options include Allium Cepa (profuse watery eyes/nose with burning, seasonal/allergic pattern), Sabadilla (paroxysmal sneezing with itchy nose/palate), Arsenicum Album (burning discharge, restlessness, worse at night), Kali Bichromicum (thick stringy discharge with sinus pain over specific pressure points). Parhez: identify and reduce exposure to personal allergic triggers (dust, pollen, pet dander) where feasible, steam inhalation, warm fluids, avoid sudden temperature changes, maintain clean bedding.",
        "piles_haemorrhoids": "Traditionally cited options include Aesculus Hippocastanum (marked sense of fullness/dryness and backache with piles), Hamamelis (bleeding piles with a sore, bruised sensation), Nux Vomica (piles with constipation from a sedentary lifestyle), Ratanhia (intense burning pain during and after passing stool). Parhez: high-fibre diet (whole grains, fruits, vegetables), adequate water intake, avoid prolonged straining or sitting, regular gentle physical activity, avoid excess spicy food if it appears to worsen symptoms.",
        "anxiety_stress_insomnia": "Traditionally cited options include Aconitum Napellus (sudden acute anxiety/panic), Argentum Nitricum (anticipatory anxiety before an event, with a hurried feeling), Ignatia Amara (anxiety/low mood following an emotional shock or grief), Gelsemium (anticipatory 'stage fright' type anxiety with trembling weakness), Coffea Cruda (mind too active/wakeful to sleep, racing thoughts). Parhez: regular sleep-wake schedule, limit caffeine especially in the afternoon/evening, reduce screen exposure before bed, regular physical activity, relaxation practices; persistent or severe anxiety, low mood, or sleep disturbance should be assessed by a qualified doctor or mental health professional.",
    },
    "parhez_general_dietary_principles": {
        "name": "Parhez - General Dietary & Lifestyle Principles in Homeopathy",
        "classical_antidote_avoidance": "Classical homeopathic teaching and most Indian manufacturer package instructions (SBL, Schwabe India, Reckeweg, Adel) advise avoiding certain strong-tasting or strongly aromatic substances around the time of taking a remedy, in the belief that these may 'antidote' (neutralise) its action: coffee and strong tea, raw onion and garlic in excess, camphor, menthol and mint (including strongly minted toothpaste, close to dosing time), strong perfumes and essential oils, tobacco, and alcohol. This is a traditional precaution rooted in homeopathic theory rather than an established pharmacological interaction, but is very widely observed in Indian homeopathic practice and stated on virtually all major-brand product labels.",
        "practical_dosing_habits": "Commonly advised practical habits: keep a gap of roughly 15-30 minutes between taking a remedy and eating, drinking, or brushing teeth; take the remedy on a clean tongue; avoid touching the pellets directly with the hand; store remedies away from direct sunlight, strong heat, and strongly-scented items; keep the bottle cap on tightly when not in use.",
        "general_wellness_principles": "Beyond remedy-specific antidote avoidance, homeopathic practitioners commonly advise general dietary and lifestyle measures consistent with broader good-health guidance: adequate hydration, a diet with sufficient fresh fruit and vegetables and limited ultra-processed food, regular sleep schedule, regular physical activity appropriate to the individual, and stress management. These general measures are sound health advice independent of homeopathic theory.",
        "when_general_parhez_is_not_enough": "For diagnosed chronic conditions (diabetes, hypertension, thyroid disorders, heart disease, kidney disease, and others), dietary management should be guided by the treating conventional physician or a registered dietitian, not solely by general homeopathic dietary tradition - homeopathic Parhez advice in such cases should be treated as complementary at most, discussed with, and not contradicting, the primary treating doctor's advice.",
    },
    "sbl_profile": {
        "name": "SBL - Company Profile",
        "history": "SBL began operations in 1983 as Sharda Boiron Laboratories Ltd., a collaboration with Laboratoires Boiron of Lyon, France (a world leader in homeopathic manufacturing since 1932). Boiron assisted in establishing SBL's original state-of-the-art, air-conditioned manufacturing facility at Sahibabad, near Delhi (Ghaziabad, Uttar Pradesh) - described by the company as the first modern homeopathic manufacturing plant in India. The company later changed its name to SBL Pvt. Ltd.",
        "manufacturing_and_scale": "SBL's manufacturing facilities today include the original Sahibabad plant plus affiliate units at Jaipur, Haridwar (I & II), and Sikkim; the company's registered office is in Haridwar, Uttarakhand. SBL describes itself as the leading homoeopathic medicines manufacturing company in India, offering generics, single remedies, bio-chemic/combination remedies, mother tinctures, dilutions, specialty tablets, herbal products, and cosmetics.",
        "product_range": "SBL's stated product range spans classical single homeopathic remedies across the standard potency scales, biochemic (Schuessler tissue salt) tablets and combinations, specialty/complex formulations for specific complaints, mother tinctures, and a wellness/personal-care product line.",
    },
    "schwabe_india_profile": {
        "name": "Dr. Willmar Schwabe India - Company Profile",
        "german_origins": "The Schwabe Group traces to Dr. Willmar Schwabe (1839-1917), a German pharmacist and early homeopathy pioneer who, dissatisfied with the inconsistent quality of homeopathic preparations of his time, founded 'Homöopatische Centralofficin Dr. Willmar Schwabe' in Leipzig in 1866. In 1872 he published the 'Pharmacopoea Homoeopathica Polyglottica', a landmark standardisation of homeopathic manufacturing methods that became a forerunner of today's Homeopathic Pharmacopoeia. The company's first order from India is stated by the company to date back over a century.",
        "india_operations": "Dr. Willmar Schwabe India Pvt. Ltd. (Schwabe India / WSI) was incorporated in 1994 and commenced production in 1997 at a dedicated manufacturing plant in Noida, Uttar Pradesh - described by the company as the only facility of its kind in India at the time, built with an emphasis on cleanliness (epoxy flooring, rounded corners, HEPA filtration). Schwabe India is the Indian subsidiary of the German Dr. Willmar Schwabe Group and carries the Group's stated 160-plus-year manufacturing heritage.",
        "product_range": "Schwabe India's stated product range includes single-remedy tablets, dilutions, mother tinctures, trituration tablets, LM potencies, biochemic tablets and bio-combinations, and specialty/complex formulations, positioned by the company as bringing German manufacturing standards to Indian-market pricing.",
    },
    "reckeweg_r_series_profile": {
        "name": "Dr. Reckeweg & Co. Germany - Company & R-Series Profile",
        "history": "The Reckeweg tradition traces to the German physician Dr. Hans-Heinrich Reckeweg (1905-1985 per most biographical sources; some sources cite an earlier Reckeweg physician 1877-1944 associated with the founding 'Eupha Laboratory'), whose work in natural/homeopathic medicine led to the establishment of Pharmazeutische Fabrik Dr. Reckeweg & Co. GmbH in Bensheim, Germany, in 1947. The company describes over 75 years of continuous 'Made in Germany' manufacturing and today distributes its preparations in more than 40 countries.",
        "r_series_concept": "Dr. Reckeweg's best-known products are the numbered 'R-series' drops (for example R1 through R89 and beyond) - complex formulations combining several homeopathic substances into a single product targeted at a named clinical complaint (for example, R5 for gastric complaints, R42 for varicose vein/circulatory support, R49 for sinus complaints, R89 for hair-related use), a different approach from classical single-remedy Hahnemannian prescribing. The company also manufactures single remedies, biochemic tablets, mother tinctures, and dilutions across standard potency scales, and states that its products are manufactured in line with German (DAB), European (Ph. Eur.), and Homeopathic Pharmacopoeia (HAB/HPUS) standards.",
        "india_distribution": "Dr. Reckeweg products sold in India are imported directly from Germany and distributed through authorised regional stockists and pharmacies rather than manufactured domestically; the brand has a long-standing distribution history in the Indian market alongside domestically-manufactured brands such as SBL and Schwabe India.",
    },
    "adel_pekana_profile": {
        "name": "Adel / PEKANA - Company Profile",
        "history_and_spagyric_method": "PEKANA Naturheilmittel GmbH was founded by pharmacist Peter Beyersdorff and Katharina Beyersdorff, based in Kisslegg in the Allgäu region of Baden-Württemberg, Germany. Following personal experience with the limitations of conventional medicine, Beyersdorff developed a range of homeopathic remedies over roughly ten years, receiving the first official manufacturing permit from the Regional Council of Karlsruhe in 1975 - the founding point of PEKANA. PEKANA's formulations describe themselves as 'homeopathic-spagyric' - combining classical homeopathic potentisation with 'spagyric' processing, a plant-extraction method with roots in alchemical tradition that separates and later recombines different components of a source plant. PEKANA's formulations were included in the first German Homeopathic Pharmacopoeia in 1991, and the company received Baden-Württemberg's Innovation Prize in 1995.",
        "adelmar_and_india": "ADELMAR PHARMA GmbH, headquartered in Forst, Germany, is the marketing/distribution partner for PEKANA's remedies internationally. In India, the brand is managed and distributed as Adel India / Adel Pharma, which states over 45 years of experience marketing and distributing homeopathic medicines in the Indian market.",
        "product_range": "Adel/PEKANA's range is centred on numbered complex homeopathic-spagyric drops (commonly cited as ADEL 1 through 87) targeted at named systems or complaints (digestive, respiratory, skin, urinary, musculoskeletal, and others), alongside a speciality range for specific conditions.",
    },
    "regulatory_evidence_status": {
        "name": "Regulatory Status & Scientific Evidence Position",
        "india_regulatory_framework": "In India, homeopathy is one of the recognised systems under the Ministry of AYUSH (Ayurveda, Yoga & Naturopathy, Unani, Siddha, Homoeopathy), established as a full ministry in 2003 (evolved from the Department of Indian Systems of Medicine & Homoeopathy, formed in 1995). The Central Council of Homoeopathy (CCH) was set up as a statutory body in 1973 under the Homoeopathy Central Council Act to regulate homeopathic education and maintain a central register of practitioners; it was reconstituted as the National Commission for Homoeopathy (NCH) on 5 July 2021. The Bachelor of Homeopathic Medicine and Surgery (BHMS) is the recognised undergraduate qualification (five and a half years including internship), and MD (Homoeopathy) is the recognised postgraduate qualification, both regulated by NCH. Only BHMS/NCH-registered practitioners are recognised as qualified homeopathic physicians in India.",
        "scientific_evidence_position": "Major independent scientific reviews have not found reliable evidence that homeopathic remedies are effective beyond a placebo response for any health condition. The Australian National Health and Medical Research Council (NHMRC), after a review of 225 controlled studies across 61 health conditions published in March 2015, concluded that 'there are no health conditions for which there is reliable evidence that homeopathy is effective' and explicitly stated that homeopathy should not be used to treat conditions that are chronic, serious, or could become serious, since choosing homeopathy over treatments with good evidence of safety and effectiveness may put a person's health at risk. The UK House of Commons Science and Technology Committee reached a similar conclusion in its 2010 report, stating that systematic reviews and meta-analyses conclusively show homeopathic products perform no better than placebo. (It should be noted that homeopathy advocacy organisations have disputed aspects of the NHMRC review's methodology; this platform presents the mainstream scientific position while noting that this is a debated topic between homeopathy's professional bodies and mainstream evidence-review bodies.)",
        "what_this_means_practically": "Homeopathy is a legally practised and regulated system of complementary medicine in India, and many people use it, particularly for minor and self-limiting complaints, generally alongside conventional care. Responsible use means: never using homeopathy as a substitute for vaccination; never using it as a substitute for evidence-based treatment of serious, chronic, worsening, or emergency conditions (including but not limited to cancer, heart disease, serious infections, diabetes, and mental health crises); always informing your conventional treating doctor about any homeopathic remedies you are taking; and consulting a registered homeopathic physician (BHMS/NCH-registered) for any actual homeopathic prescription rather than self-treating based on general reference information such as this platform provides.",
    },
    "india_homeopathy_context": {
        "name": "Homeopathy in India - Context",
        "adoption_and_scale": "India has one of the largest homeopathic practitioner bases and patient populations in the world, with homeopathy formally integrated into the national AYUSH healthcare framework alongside Ayurveda, Yoga & Naturopathy, Unani, and Siddha. Government homeopathic dispensaries and hospitals operate in many states alongside a very large private-practice sector, and homeopathic medicines are widely available through pharmacies and, increasingly, online retailers.",
        "manufacturing_hub": "India hosts substantial domestic homeopathic manufacturing capacity (led by companies such as SBL and Dr. Willmar Schwabe India, both with large modern plants in the Delhi NCR region - Sahibabad/Ghaziabad and Noida respectively) alongside imported German brands (Dr. Reckeweg, Adel/PEKANA) distributed through authorised Indian channels, making India both a major consumption market and a significant manufacturing base for homeopathic medicines globally.",
        "research_institutions": "The Central Council for Research in Homoeopathy (CCRH), under the Ministry of AYUSH, is India's apex research body for homeopathy, conducting clinical research, drug proving studies, and organising national awareness events, including around World Homeopathy Day (10 April) each year.",
        "affordability_and_access": "Homeopathic consultation and medicines are generally positioned as a comparatively low-cost treatment option in India relative to many specialist conventional treatments, which is frequently cited as a factor in its widespread public adoption, alongside cultural familiarity and a long regulatory history in the country.",
    },
}

def save_knowledge():
    with open(DATA_DIR / "homeo_knowledge.json", "w", encoding="utf-8") as f:
        json.dump(KNOWLEDGE, f, indent=2, ensure_ascii=False)

def load_sessions():
    sf = DATA_DIR / "sessions.json"
    if sf.exists():
        with open(sf) as f: return json.load(f)
    return {}

def save_session(sid, data):
    sessions = load_sessions()
    sessions[sid] = {**data, "updated": datetime.datetime.now().isoformat()}
    with open(DATA_DIR / "sessions.json", "w") as f: json.dump(sessions, f, indent=2)

def is_online():
    if not REQUESTS_OK: return False
    try: req_lib.get("https://8.8.8.8", timeout=3); return True
    except: return False

def extract_pdf_text(filepath):
    if not FITZ_OK: return "[PDF extraction unavailable]"
    try:
        doc = fitz.open(str(filepath))
        text = "".join(page.get_text() for page in doc)
        doc.close(); return text[:8000]
    except Exception:
        # SOFTWARESAFETY: never leak internal exception/stack trace details to caller
        return "[PDF extraction error]"

DEFAULT_SYSTEM = (
    "You are HomeoCare AI, a research and educational assistant describing homeopathy "
    "as a system of medicine, following classical homeopathic case-taking methodology "
    "(Hahnemann's Organon, Boericke's and Kent's Materia Medica) and covering Indian "
    "and German homeopathic manufacturers (SBL, Dr. Willmar Schwabe India, Dr. Reckeweg "
    "& Co., ADEL/PEKANA). "
    "ALWAYS start with a brief AI research disclaimer. "
    "When asked to analyse a case, ask or synthesise a thorough case picture covering "
    "mental/emotional generals, physical generals (thermal reaction, thirst, food "
    "desires/aversions, sleep, perspiration), particular symptoms and modalities, and "
    "causation, in the style of classical homeopathic case-taking - then, if enough "
    "information is present, suggest 2-4 commonly indicated remedies per classical "
    "materia medica with typical potency conventions AND a detailed 'Parhez' (diet and "
    "lifestyle do's and don'ts) relevant to the case. "
    "ALWAYS clearly state that this is educational information reflecting traditional "
    "homeopathic practice, not a diagnosis or prescription, that mainstream systematic "
    "reviews (NHMRC 2015, UK S&T Committee 2010) have not found reliable evidence of "
    "effectiveness beyond placebo, and that a registered homeopathic physician (BHMS/NCH) "
    "should be consulted for any actual prescription. NEVER suggest homeopathy as a "
    "substitute for vaccination or for evidence-based treatment of serious, chronic, or "
    "emergency conditions - for those, and for any emergency, advise consulting a "
    "conventional doctor or calling 112/999/911 immediately. Reference AYUSH/NCH "
    "regulatory context for Indian users where relevant."
)

def call_ai(prompt, system_prompt=None, max_tokens=2500, provider=None, api_key=None):
    if not AI_PROVIDERS_OK: return None, "ai_providers_missing"
    provider = validate_provider(provider)
    effective_key = (sanitise_api_key(api_key) or
                     DEFAULT_PROVIDER_KEYS.get(provider, "") or
                     (API_KEY if provider == "anthropic" else ""))
    if not effective_key or not REQUESTS_OK or not is_online():
        return None, "offline_or_no_key"
    text, mode = ai_providers.call_ai(
        provider, effective_key, prompt, system_prompt or DEFAULT_SYSTEM, max_tokens
    )
    if text is None:
        log.error(f"{provider} API error: {mode}")
        return None, mode
    return text, "live_ai"

def build_offline_response(topic, patient_info=None):
    topic_l = topic.lower()
    kb_key = next(
        (k for k in KNOWLEDGE
         if k.replace("_", " ") in topic_l or topic_l in k.replace("_", " ")
         or any(w in topic_l for w in k.split("_"))),
        None
    )
    lines = [
        "# HomeoCare AI Research Report",
        f"**Topic:** {topic}",
        "**Mode:** Offline Research (Embedded Homeopathy Knowledge Base)",
        "",
        "> DISCLAIMER: Educational information reflecting classical homeopathic "
        "practice and Indian/German manufacturer literature. NOT a diagnosis or "
        "prescription. Mainstream reviews (NHMRC 2015, UK S&T Committee 2010) found "
        "no reliable evidence of effect beyond placebo. Never a substitute for "
        "vaccination or evidence-based treatment of serious/chronic/emergency "
        "conditions. ALWAYS consult a registered homeopathic physician (BHMS/NCH). "
        "EMERGENCY: Call 112 (India) / 999 (UK) / 911 (US).",
        "", "---", ""
    ]
    if kb_key:
        kb = KNOWLEDGE[kb_key]
        lines.append(f"## {kb.get('name', topic)}\n")
        for field, value in kb.items():
            if field == "name": continue
            if isinstance(value, str):
                lines += [f"**{field.replace('_', ' ').title()}:** {value}", ""]
    else:
        lines += [f"## Research Overview: {topic}", "",
                  f"Enable live AI in Settings for detailed research on {topic}.", ""]
    lines += [
        "---",
        "## Regulatory & Reference Resources (India)",
        "- Ministry of AYUSH: ayush.gov.in",
        "- National Commission for Homoeopathy (NCH): nch.org.in",
        "- Central Council for Research in Homoeopathy (CCRH): under Ministry of AYUSH",
        "- Emergency: 112",
        "",
        f"WARNING - {DISCLAIMER}"
    ]
    return "\n".join(lines)

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(str(STATIC_DIR), filename)

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": VERSION,
                    "online": is_online(), "pdf_extract": FITZ_OK,
                    "timestamp": datetime.datetime.now().isoformat()})

@app.route("/api/upload", methods=["POST"])
def upload():
    if "files" not in request.files: return jsonify({"error": "No files"}), 400
    session_id = request.form.get("session_id") or str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id; session_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for f in request.files.getlist("files"):
        if not f.filename: continue
        ext = Path(f.filename).suffix.lower()
        # SOFTWARESAFETY: never trust client filename — generate opaque server-side name
        safe = f"{uuid.uuid4().hex}{ext}"; dest = session_dir / safe; f.save(str(dest))
        extracted = extract_pdf_text(dest) if ext == ".pdf" else ""
        results.append({"original": f.filename, "saved": safe,
                        "type": "pdf" if ext == ".pdf" else ("image" if ext in [".jpg",".jpeg",".png"] else "text"),
                        "size_kb": round(dest.stat().st_size/1024, 1), "has_content": bool(extracted)})
    existing = load_sessions().get(session_id, {})
    save_session(session_id, {"session_id": session_id, "files": existing.get("files",[]) + results})
    return jsonify({"success": True, "session_id": session_id,
                    "uploaded": len(results), "files": results, "disclaimer": DISCLAIMER})

@app.route("/api/condition/<condition_name>")
def condition_detail(condition_name):
    cn = sanitise_text_field(condition_name, 100).lower().replace("-","_").replace(" ","_")
    if cn in KNOWLEDGE:
        return jsonify({"success": True, "mode": "offline_kb",
                        "condition": KNOWLEDGE[cn], "disclaimer": DISCLAIMER})
    provider = validate_provider(request.args.get("provider","anthropic"))
    effective_key = (sanitise_api_key(request.args.get("api_key","")) or
                     DEFAULT_PROVIDER_KEYS.get(provider,"") or
                     (API_KEY if provider=="anthropic" else ""))
    safe_name = sanitise_text_field(condition_name, 100)
    prompt = (f"Research on the homeopathic approach to {safe_name}, per classical "
              "materia medica and Indian manufacturer literature (SBL, Schwabe India, "
              "Reckeweg, Adel/Pekana): typically cited remedies with symptom "
              "differentiation, typical potency conventions, and detailed Parhez "
              "(diet/lifestyle guidance). Include the evidence-status disclaimer.")
    result, mode = call_ai(prompt, provider=provider, api_key=effective_key)
    if not result: result = build_offline_response(safe_name); mode = "offline"
    return jsonify({"success": True, "mode": mode, "content": result, "disclaimer": DISCLAIMER})

@app.route("/api/casetaking/analyse", methods=["POST"])
def casetaking_analyse():
    """Deep homeopathic case-taking analysis endpoint - the flagship feature."""
    data = request.json or {}
    if not rate_limit_check(): return jsonify({"error": "Rate limit exceeded"}), 429
    provider = validate_provider(data.get("provider","anthropic"))
    effective_key = (sanitise_api_key(data.get("api_key","")) or
                     DEFAULT_PROVIDER_KEYS.get(provider,"") or
                     (API_KEY if provider=="anthropic" else ""))

    fields = {
        "chief_complaint": sanitise_text_field(data.get("chief_complaint",""), 400),
        "duration": sanitise_text_field(data.get("duration",""), 100),
        "age": sanitise_text_field(str(data.get("age","")), 10),
        "gender": sanitise_text_field(data.get("gender",""), 30),
        "mental_emotional": sanitise_text_field(data.get("mental_emotional",""), 500),
        "fears": sanitise_text_field(data.get("fears",""), 300),
        "thermal_reaction": sanitise_text_field(data.get("thermal_reaction",""), 100),
        "thirst": sanitise_text_field(data.get("thirst",""), 200),
        "food_desires": sanitise_text_field(data.get("food_desires",""), 300),
        "food_aversions": sanitise_text_field(data.get("food_aversions",""), 300),
        "sleep_dreams": sanitise_text_field(data.get("sleep_dreams",""), 300),
        "perspiration": sanitise_text_field(data.get("perspiration",""), 200),
        "particular_symptoms": sanitise_text_field(data.get("particular_symptoms",""), 500),
        "aggravation": sanitise_text_field(data.get("aggravation",""), 300),
        "amelioration": sanitise_text_field(data.get("amelioration",""), 300),
        "causation": sanitise_text_field(data.get("causation",""), 300),
        "history": sanitise_text_field(data.get("history",""), 400),
    }
    if not fields["chief_complaint"]:
        return jsonify({"error": "Chief complaint is required"}), 400

    case_summary = "\n".join(f"{k.replace('_',' ').title()}: {v}" for k, v in fields.items() if v)
    prompt = (
        "Homeopathic Case-Taking Analysis Request (educational/research context).\n"
        f"{case_summary}\n\n"
        "Acting as a classical homeopathic case-analysis assistant: "
        "1) Summarise the totality of symptoms (mental generals, physical generals, "
        "particulars, modalities, causation) as a homeopath would organise them. "
        "2) Suggest 2-4 commonly indicated remedies per classical materia medica that "
        "best match this symptom picture, explaining the reasoning/differentiation "
        "between them. 3) For each, note typical potency conventions used in Indian "
        "practice (e.g., 30C, 200C) as general reference only. 4) Provide detailed "
        "Parhez (diet and lifestyle do's and don'ts) relevant to this case. "
        "5) End with the standard disclaimer: this is educational information, not a "
        "diagnosis or prescription; mainstream reviews have not found reliable "
        "evidence of effect beyond placebo; a registered homeopathic physician "
        "(BHMS/NCH) should be consulted for actual treatment; never delay conventional "
        "care for anything serious or an emergency."
    )
    result, mode = (call_ai(prompt, provider=provider, api_key=effective_key, max_tokens=3000)
                    if (effective_key and is_online()) else (None, "offline"))
    if not result:
        result = (
            "# Case-Taking Summary (Offline Mode)\n\n"
            f"**Chief Complaint:** {fields['chief_complaint']}\n\n"
            "Enable live AI in Settings for a full case analysis with remedy "
            "differentiation and detailed Parhez. In the meantime, browse the "
            "Materia Medica and Common Conditions sections for traditional remedy "
            "reference matching your symptom pattern.\n\n"
            f"WARNING - {DISCLAIMER}"
        )
        mode = "offline"
    return jsonify({"success": True, "mode": mode, "analysis": result,
                    "disclaimer": DISCLAIMER,
                    "timestamp": datetime.datetime.now().isoformat()})

@app.route("/api/chat/send", methods=["POST"])
def chat_send():
    data = request.json or {}
    if not rate_limit_check(): return jsonify({"error": "Rate limit exceeded"}), 429
    message = sanitise_text_field(data.get("message",""), 1000)
    if not message: return jsonify({"error": "Empty message"}), 400
    provider = validate_provider(data.get("provider","anthropic"))
    effective_key = (sanitise_api_key(data.get("api_key","")) or
                     DEFAULT_PROVIDER_KEYS.get(provider,"") or
                     (API_KEY if provider=="anthropic" else ""))
    result = None
    if data.get("request_ai") and is_online() and effective_key:
        result, _ = call_ai(
            f"Homeopathy question: '{message}'. 3-4 paragraphs, reference classical "
            "materia medica and/or Indian manufacturer (SBL/Schwabe India/Reckeweg/Adel) "
            "context where relevant. Include Parhez guidance if the question is about a "
            "condition or remedy. End with the standard disclaimer and registered "
            "homeopath (BHMS/NCH) consultation reminder. If this concerns a serious, "
            "chronic, or emergency situation, or vaccination, advise conventional "
            "medical care/112/999/911 first.",
            max_tokens=800, provider=provider, api_key=effective_key)
    return jsonify({"success": True, "ai_response": result,
                    "disclaimer": "Educational information only. Consult a registered homeopathic physician (BHMS/NCH)."})

@app.route("/api/report/generate", methods=["POST"])
def generate_report():
    data = request.json or {}
    if not rate_limit_check(): return jsonify({"error": "Rate limit exceeded"}), 429
    topic = sanitise_text_field(data.get("topic","General Homeopathy Research"), 200)
    patient = data.get("patient_info", {}) if isinstance(data.get("patient_info"), dict) else {}
    provider = validate_provider(data.get("provider","anthropic"))
    effective_key = (sanitise_api_key(data.get("api_key","")) or
                     DEFAULT_PROVIDER_KEYS.get(provider,"") or
                     (API_KEY if provider=="anthropic" else ""))
    content = build_offline_response(topic, patient)
    if effective_key and is_online():
        ai_content, _ = call_ai(
            f"Generate a comprehensive homeopathy research report for: {topic}. "
            f"Context: {patient}. Cover traditional remedy options, potency "
            "conventions, detailed Parhez, and the evidence-status disclaimer.",
            max_tokens=3500, provider=provider, api_key=effective_key)
        if ai_content: content = ai_content
    # SOFTWARESAFETY: opaque, non-sequential identifier — not a predictable/enumerable integer ID
    report_id = f"report_{uuid.uuid4().hex}"
    report = {"report_id": report_id, "generated": datetime.datetime.now().isoformat(),
              "topic": topic, "patient": patient, "content": content, "disclaimer": DISCLAIMER}
    with open(REPORTS_DIR / f"{report_id}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return jsonify(report)

@app.route("/api/resolve", methods=["POST"])
def resolve_multi_ai():
    data = request.json or {}
    if not rate_limit_check(): return jsonify({"error": "Rate limit exceeded"}), 429
    prompt = sanitise_text_field(data.get("prompt",""), 4000)
    if not prompt: return jsonify({"error": "No prompt provided"}), 400
    pairs_raw = data.get("providers",[])
    if not isinstance(pairs_raw, list) or len(pairs_raw) < 1:
        return jsonify({"error": "No providers specified"}), 400
    if not AI_PROVIDERS_OK: return jsonify({"error": "ai_providers module not available"}), 500
    pairs = []
    for p in pairs_raw[:6]:
        if not isinstance(p, dict): continue
        pid = validate_provider(p.get("provider",""))
        key = sanitise_api_key(p.get("key",""))
        if pid and key: pairs.append((pid, key))
    if not pairs: return jsonify({"error": "No valid provider+key pairs"}), 400
    results = ai_providers.call_multi_ai(pairs, prompt, DEFAULT_SYSTEM, 1500)
    successes = [r for r in results if r.get("success") and r.get("text")]
    synthesis = None
    if len(successes) >= 2:
        synth_parts = [f"=== {r.get('label',r.get('provider','AI'))} ===\n{(r.get('text') or '')[:1200]}"
                       for r in successes]
        synth_prompt = (
            "You are a homeopathy research synthesis engine. Multiple AI systems "
            "answered the same question. Question: " + prompt + "\n\n" +
            "\n\n".join(synth_parts) + "\n\n"
            "Synthesise the best, most complete, evidence-grounded answer per classical "
            "homeopathic literature. Note any disagreements. Include Parhez guidance if "
            "relevant. Remind that this is educational information only, not a "
            "prescription, and that a registered homeopathic physician (BHMS/NCH) "
            "should be consulted."
        )
        synth_key = next((k for pr,k in pairs if pr==successes[0]["provider"]), None)
        if synth_key:
            synth_text, _ = ai_providers.call_ai(
                successes[0]["provider"], synth_key, synth_prompt,
                "You are a homeopathy research synthesis assistant.", 2000)
            synthesis = synth_text
    return jsonify({"success": True, "responses": results,
                    "synthesis": synthesis, "disclaimer": DISCLAIMER})

@app.route("/api/providers")
def list_providers():
    if not AI_PROVIDERS_OK: return jsonify({"providers": [], "error": "ai_providers module not available"})
    return jsonify({"providers": [
        {"id":k,"label":v["label"],"default_model":v["default_model"],
         "key_prefix":v["key_prefix"],"get_key_url":v["get_key_url"],
         "server_default_configured":bool(DEFAULT_PROVIDER_KEYS.get(k))}
        for k,v in ai_providers.PROVIDERS.items()], "online": is_online()})

@app.route("/api/status")
def status():
    any_key = bool(API_KEY) or any(DEFAULT_PROVIDER_KEYS.values())
    return jsonify({"server":"running","version":VERSION,"online":is_online(),
                    "mode":"live_ai" if (any_key and is_online()) else "offline_research",
                    "capabilities":{"pdf":FITZ_OK,"images":PIL_OK,
                                    "live_ai":bool(any_key and is_online()),
                                    "offline":True,"multi_provider":AI_PROVIDERS_OK,
                                    "rate_limiting":True,"aes256_frontend":True,
                                    "ambiguity_resolver":True},
                    "knowledge_base":list(KNOWLEDGE.keys()),
                    "providers":list(ai_providers.PROVIDERS.keys()) if AI_PROVIDERS_OK else [],
                    "disclaimer":DISCLAIMER})

# SOFTWARESAFETY: opaque fault management — never leak stack traces or internals to client
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    err_ref = uuid.uuid4().hex[:12]
    log.error(f"[{err_ref}] Internal server error: {e}")
    return jsonify({"error": "Internal server error", "reference": err_ref}), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    save_knowledge()
    log.info("="*60)
    log.info(f"  HomeoCare AI Server v{VERSION} - Port {args.port}")
    log.info(f"  Online: {is_online()}")
    log.info(f"  URL: http://localhost:{args.port}")
    log.info(f"  Providers: {list(ai_providers.PROVIDERS.keys()) if AI_PROVIDERS_OK else 'N/A'}")
    log.info("="*60)
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True, use_reloader=False)
