# alysa

Projektet består av en frontend där användaren laddar upp PDF-filer och en lokal backend som extraherar text, använder OCR vid behov och returnerar strukturerad JSON redo för vidare analys. AI-modellen är ännu inte inkopplad; nuvarande pipeline säkerställer korrekt och pålitlig rådata.

alysa kan idag:

- ta emot PDF-filer via webbläsare
- extrahera text direkt eller via OCR för skannade dokument
- dela upp text i enskilda meningar
- identifiera och klassificera SKALL- och BÖR-krav
- visa resultaten i webbläsaren och erbjuda nedladdning som JSON

Tekniskt bygger projektet på FastAPI i backend och en statisk frontend (HTML, Tailwind CSS, JavaScript). PDF-hantering sker via PyMuPDF, OCR via Tesseract och pdf2image.

För att köra projektet lokalt krävs Python 3.10+, Tesseract OCR samt Poppler. Efter installation av Python-beroenden startas backend med:

python -m uvicorn main:app --reload

Frontend körs genom att öppna index.html i webbläsaren och kommunicerar då med den lokala backend-servern.

Projektet är i ett stabilt tidigt skede och utgör grunden för kommande AI-baserad kravanalys och juridisk granskning.

Länk: https://gupr.github.io/alysa

https://github.com/oscoro123/Alysa_mvp
