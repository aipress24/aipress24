# AIPress24

# Troubleshooting / FAQ Guide

Some common issues and solutions when deploying.

## MacOS

### CERTIFICATE_VERIFY_FAILED

- Error message: `urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate`

- Run the followin commands:

```
pip install certifi
sudo /Applications/Python\ 3.12/Install\ Certificates.command
```

#### DB missing : Could not parse SQLAlchemy URL

(Assuming using Postgresql)

- Error message: `Could not parse SQLAlchemy URL from string`

- Try to declare the DB URI with no '"' around the URI string, like:

`export FLASK_SQLALCHEMY_DATABASE_URI=postgresql://localhost/aipress24`


#### DB missing

(Assuming using Postgresql)

- Error message: `FATAL: database "localhost/aipress24" does not exist`

- just init the db (see the flask/cli/db2 commands) :

```bash
flask db2 initdb
```

#### reminder to install start once Postgresql

```
brew services run postgresql
```


#### connection failed

- Error like:
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

- restart the DB:
```
brew services run postgresql
```


#### localhost:5000 nost responding

- After `make run`, if `localhost:5000` is not responding but `127.0.0.1:5000` is

- No solution found ?

- Maybe: shutdown AirPlay service inmac  preferences ?


- `make test`  and message is:

```
ERROR src/app/ui/macros/images_test.py::test_profile_image - sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (::1), port 5432 failed: FATAL:  database "aipress24_test...
```

#### `aut_user` missing

- At connection /registration:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "aut_user" does not exist
LINE 3: FROM aut_user
^
```

- just create the DB:

```bash
flask db2 initdb
```

#### `RuntimeError: The configuration value `SECURITY_PASSWORD_SALT ...`


- At /registration, runtime error:

```
File "/Users/jd/p312a/lib/python3.12/site-packages/flask_security/utils.py", line 338, in get_hmac
raise RuntimeError(
^
RuntimeError: The configuration value `SECURITY_PASSWORD_SALT` must not be None when the value of `SECURITY_PASSWORD_HASH` is set to "bcrypt"
```

- just provide secret key:

```bash
export FLASK_SECURITY_PASSWORD_SALT="some secret key"
```

#### assert error on missing 'box'

- after connection:
```
File "/Users/jd/dev/abi/gits/aipress24-flask/src/app/templates/macros/promo.j2", line 3, in template
{% set box = get_promotion(id) %}
File "/Users/jd/dev/abi/gits/aipress24-flask/src/app/services/promotions.py", line 16, in get_promotion
assert box
^^^^^^^^^^
```
- just boostrap the app:

```bash
flask bootstrap
```

#### error on weasyprint and gobject-2.0-0

- error like: "cannot load library 'gobject-2.0-0'"

- lot of links to add after installing packages via `brew`

-> `brew install weasyprint`

still pb ->
```
sudo ln -s /opt/homebrew/opt/glib/lib/libgobject-2.0.0.dylib /usr/local/lib/gobject-2.0
sudo ln -s /opt/homebrew/opt/pango/lib/libpango-1.0.dylib /usr/local/lib/pango-1.0
sudo ln -s /opt/homebrew/opt/harfbuzz/lib/libharfbuzz.dylib /usr/local/lib/harfbuzz
sudo ln -s /opt/homebrew/opt/fontconfig/lib/libfontconfig.1.dylib /usr/local/lib/fontconfig-1
sudo ln -s /opt/homebrew/opt/pango/lib/libpangoft2-1.0.dylib /usr/local/lib/pangoft2-1.0
```

#### FileNotFoundError magnifying-glass.svg

FileNotFoundError: [Errno 2] No such file or directory: '/Users/jd/p312a/lib/python3.12/icons/svg/outline/magnifying-glass.svg'

- home_path
def get_home_path() -> Path:
    return (Path(current_app.root_path) / ".." / ".." / "..").resolve()

-> no pip install, juste poetry install and run from top project ?


#### No module named 'app'

```
python scripts/generate-forms3.py
Traceback (most recent call last):
  File "/Users/jd/dev/abi/gits/aipress24-flask/scripts/generate-forms3.py", line 13, in <module>
    from app.modules.wip.forms import (
ModuleNotFoundError: No module named 'app'
make: *** [run] Error 1
```

```
flask vite install
Usage: flask vite install [OPTIONS]
Try 'flask vite install --help' for help.

Error: While importing 'wsgi', an ImportError was raised:

Traceback (most recent call last):
  File "/Users/jd/dev/abi/gits/aipress24-flask/.venv/lib/python3.12/site-packages/flask/cli.py", line 245, in locate_app
    __import__(module_name)
  File "/Users/jd/dev/abi/gits/aipress24-flask/wsgi.py", line 9, in <module>
    from app.flask.main import create_app
ModuleNotFoundError: No module named 'app'
```

-> use : `pip install -e .` then `make run`
