# End-to-end tests (using Playwright)

To run the tests, use the following command:

```bash
playwright install # only needed once
python e2e-tests/test_journaliste.py
```

If you want to test another URL than the default one, you can use the `ROOT_URL` environment variable:

```bash
ROOT_URL=http://localhost:5000/ python e2e-tests/test_journaliste.py
```
