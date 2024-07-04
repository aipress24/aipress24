

## Generate data:

```
./make_ontology_data.sh Ontologies-34_fix.xlsx
```


## Origin of data:

- `towns` directory
    - each file name is iso3 code of a country
    - each file contains zip_code and area name of zip_code

    data comes from :
    https://download.geonames.org/export/zip/allCountries.zip

    See project `geonames-sandbox` for scripts.

- `civilite.json` : done by hand
- `pays.json` : data coming from gouv.fr, list of iso3 code and official names of countries (in french)

- all other files:
```
agencesrp.json
centres-d-interet-associations.json
centres-d-interet-organisations.json
centres-d-interet-politiques-ad.json
competences-en-journalisme.json
competencesexperts.json
fonctions-associations-syndicat.json
fonctions-du-journalisme.json
fonctions-organisations-privees.json
fonctions-politiques-administra.json
langues.json
metiers.json
newsrooms.json
secteurs-detailles.json
tailles-dorganisation.json
types-de-presse-medias.json
types-dentreprises-de-presse.json
types-dorganisation.json
```
