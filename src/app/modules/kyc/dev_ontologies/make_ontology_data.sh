#!/bin/bash

[ -f split_ontologies.py ] || {
    echo "Script need to be run locally"
    exit 1
}

path="$1"

[ -f "${path}" ] || {
    echo "File not found: '${path}'"
    exit 1
}

/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to ods ${path} || exit 1

ods="${path%%.*}.ods"
json="current.json"
odsparsator -m ${ods} ${json}
rm -f ${ods}

rm -fr ontology_json
python split_ontologies.py || exit 1
rm -fr data
python make_value_label.py || exit 1

rm -fr ../data
mv data ..
ls -lrth ../data
