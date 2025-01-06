# Standards used by Aipress24

## Technical standards

* **PEP 8:** The style guide for Python code. This is indicated in the "Code Style" section.
* **HTML5 (HTML, CSS, JavaScript) Standards:** the project follows modern web standards for HTML, CSS, and JavaScript.
* **SQL Standards:** The projects uses SQLAlchemy as an abstraction layer over SQL. It currently supports PostgreSQL and Sqlite3. MySQL might be supported in the future.
* **RESTful API Design Principles:** The platform will provide API which will follow RESTful principles (including OpenAPI descriptions).

## Licensing & metadata standards

* **REUSE Specification 3.0:** The project is compliant with this specification for clear and unambiguous licensing information (as checked with the `reuse lint` command).
* **Publiccode.yml:** The project provides a `publiccode.yml` file to describe the project's metadata.

## Business standards, formats and ontologies

* **IPTC**: The project aims to adhere to the International Press Telecommunications Council standards for news content (https://cv.iptc.org/newscodes/). However, because the IPTC ontology does not map well with TCA's business practices, we do not implement the full standard. A third-party who would wish to use the IPTC ontology could do so by inserting the proper ontology in the database.
* **Dublin Core Metadata Initiative (DCMI):** The project data model reuses some of the Dublin Core Metadata Initiative terms.
* **microformats.org**: The project data model reuses some of the microformats.org terms.
* **Schema.org**: The project data model reuses some of the Schema.org terms.
* **Open Graph Protocol**: The project uses the Open Graph Protocol to provide metadata for social media sharing.
* **Journalistic Standards:** The project aims to adhere to journalistic standards (cf. https://en.wikipedia.org/wiki/Journalism_ethics_and_standards for reference). This includes standards related to accuracy, fairness, and transparency in reporting.

## Standards that may be implemented in the future

(Cf. the roadmap)

* **RSS:** The roadmap mentions "Personalized RSS Feeds," so the project will likely adhere to RSS standards.
* **ActivityPub:** For federated content sharing. This is a W3C standard for decentralized social networking.
* **OAuth 2.0 or OpenID Connect:** If / when the project implements user authentication with external providers, these standards will be used.
* **Journalism Trust Initiative (JTI):** Mentioned in the roadmap for aligning certifications with JTI standards. This indicates an intent to adhere to standards related to journalistic ethics and transparency.
