This directory contains data that may be used to update data of the application:

 - Geographical data (countries, zip codes)
 - at date of august 7, 2026:
    - 108 countries have zip code (some zip codes are partial for copyright reasons)
    - 2016 country names
 
 ## Origin of data:
 
 - `towns` directory
     - each file name is iso3 code of a country
     - each file contains zip_code and area name of zip_code
 
     data comes from :
     https://download.geonames.org/export/zip/allCountries.zip
 
     See project `geonames-sandbox` for scripts.
 
 - `pays.json` : data coming from gouv.fr, list of iso3 code and official names of countries (in french)
