
## Generate data for DB:

This countries and zip code data are used by the `flask ontologies import` script.

Note: only countries which have a zip_code entry are kept in the select list of countries.

## Origin of data:

- `towns` directory
    - each file name is iso3 code of a country
    - each file contains zip_code and area name of zip_code

    data comes from :
    https://download.geonames.org/export/zip/allCountries.zip

    See project `geonames-sandbox` for scripts.

- `pays.json` : data coming from gouv.fr, list of iso3 code and official names of countries (in french)
