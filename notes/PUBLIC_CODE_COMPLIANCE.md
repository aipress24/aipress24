# Standard for Public Code version 0.8.0 Compliance Review for Aipress24

NOTE: this is a work in progress. Take with a grain of salt (or submit a PR to help improve it).

**Legend:**

*   **✓** - Likely Compliant
*   **?** - Partially Compliant or Needs More Information
*   **✗** - Likely Non-Compliant
*   **N/A** - Not Applicable

**Checklist Evaluation:**

**Code in the open:**

*   **✓**  All source code for any software in use (unless used for fraud detection) MUST be published and publicly accessible. - **The project is on GitHub, indicating open source.**
*   **✓**  All source code for any policy in use (unless used for fraud detection) MUST be published and publicly accessible. - **Assuming policy is embedded in code and documentation, it's publicly accessible.**
*   **✓**  The codebase MUST NOT contain sensitive information regarding users, their organization or third parties.
*   **✓**  Any source code not currently in use (such as new versions, proposals or older versions) SHOULD be published. - **Done through Git practices like branching and tagging.**
*   **N/A** Documenting which source code or policy underpins any specific interaction the general public may have with an organization is OPTIONAL. - **Not applicable at this stage.**

**Bundle policy and source code:**

*   **?**  The codebase MUST include the policy that the source code is based on. - **The policy isn't explicitly stated as a separate document in the README. It might be implicitly embedded in the documentation and code, which needs to be verified.**
*   **?**  If a policy is based on source code, that source code MUST be included in the codebase, unless used for fraud detection. - **Assuming policy is derived from the code, this is likely true.**
*   **?**  Policy SHOULD be provided in machine-readable and unambiguous formats. - **Unclear without seeing how the policy is documented.**
*   **?**  Continuous integration tests SHOULD validate that the source code and the policy are executed coherently. - **Cannot be determined from the README. Needs investigation of CI setup.**

**Make the codebase reusable and portable:**

*   **✓**  The codebase MUST be developed to be reusable in different contexts. - **The codebase can be reused in independent instances of the application, configured through environment variables.**
*   **✓**  The codebase MUST be independent from any secret, undisclosed, proprietary, or non-open licensed software or services for execution and understanding.
*   **✗**  The codebase SHOULD be in use by multiple parties. - **The project is new, so it's not true yet.**
*   **?**  The roadmap SHOULD be influenced by the needs of multiple parties. - **The roadmap demonstrates an intention to be open to community contributions, suggesting influence from multiple parties, but this is in the future.**
*   **?**  The development of the codebase SHOULD be a collaboration between multiple parties. - **While open to contributions, it's not clear if there's active multi-party development yet. The project is quite young.**
*   **?**  Configuration SHOULD be used to make source code adapt to context specific needs. - **Cannot be determined definitively from the README. Likely to use configuration files, but needs confirmation.**
*   **?**  The codebase SHOULD be localizable. - **The roadmap mentions "Localization and Regional Adaptations", but the current state is unknown.**
*   **?**  Source code and its documentation SHOULD NOT contain situation-specific information. - **Cannot be fully determined from the README. Requires code and documentation review.**
*   **?**  Codebase modules SHOULD be documented in such a way as to enable reuse in codebases in other contexts. - **Cannot be fully determined without reviewing the code documentation. The roadmap suggests this as a goal.**
*   **?**  The software SHOULD NOT require services or platforms available from only a single vendor. - **Generally true based on the tech stack. However, Heroku deployment instructions might indicate a temporary reliance on a single vendor until other deployment options are fully fleshed out. Needs further investigation regarding S3 compatibility.**

**Welcome contributors:**

*   **✓**  The codebase MUST allow anyone to submit suggestions for changes to the codebase. - **GitHub allows this through pull requests.**
*   **✓**  The codebase MUST include contribution guidelines explaining what kinds of contributions are welcome and how contributors can get involved, for example in a `CONTRIBUTING` file. - **The README has a detailed "Contributing" section.**
*   **?**  The codebase MUST document the governance of the codebase, contributions and its community, for example in a `GOVERNANCE` file. - **Not explicitly mentioned in the README, but elements of governance are present in the "Contributing" and "Code of Conduct" sections. A dedicated `GOVERNANCE` file would be clearer.**
*   **?**  The contribution guidelines SHOULD document who is expected to cover the costs of reviewing contributions. - **Implicitly, this would be the maintainers, but it's not explicitly stated.**
*   **?**  The codebase SHOULD advertise the committed engagement of involved organizations in the development and maintenance. - **Techno-Chroniqueurs Associés and Abilian are mentioned, but their level of ongoing commitment is not explicitly stated.**
*   **✓**  The codebase SHOULD have a publicly available roadmap. - **The README includes a detailed roadmap.**
*   **?**  The codebase SHOULD publish codebase activity statistics. - **GitHub provides some activity statistics, but it's not clear if they are actively published or highlighted.**
*   **✓**  Including a code of conduct for contributors in the codebase is OPTIONAL. - **The project has a `CODE_OF_CONDUCT.md`.**

**Make contributing easy:**

*   **✓**  The codebase MUST have a public issue tracker that accepts suggestions from anyone. - **GitHub issues fulfill this.**
*   **✓**  The documentation MUST link to both the public issue tracker and submitted codebase changes, for example in a `README` file. - **The README links to the issue tracker.**
*   **✓**  The codebase MUST have communication channels for users and developers, for example email lists. - **The README mentions GitHub discussions.**
*   **?**  There MUST be a way to report security issues for responsible disclosure over a closed channel. - **Not explicitly mentioned in the README. This is a crucial requirement that needs to be addressed.**
*   **?**  The documentation MUST include instructions for how to report potentially security sensitive issues. - **Absent from the README. Needs to be added.**

**Maintain version control:**

*   **✓**  All files in the codebase MUST be version controlled. - **It's on GitHub, so this is highly likely.**
*   **?**  All decisions MUST be documented in commit messages. - **Cannot be fully determined without examining the commit history. However, the "Contribution Guidelines" encourage meaningful commit messages.**
*   **?**  Every commit message MUST link to discussions and issues wherever possible. - **Cannot be fully determined without examining the commit history. Good practice, but not enforced by GitHub.**
*   **✓**  The codebase SHOULD be maintained in a distributed version control system. - **Git is a DVCS.**
*   **✓**  Contribution guidelines SHOULD require contributors to group relevant changes in commits. - **The "Contribution Guidelines" implicitly suggest this by advocating for feature branches and meaningful commit messages.**
*   **?**  Maintainers SHOULD mark released versions of the codebase, for example using revision tags or textual labels. - **Cannot be determined from the README. Standard practice for mature projects, but might not be implemented yet for a new project.**
*   **✓**  Contribution guidelines SHOULD encourage file formats where the changes within the files can be easily viewed and understood in the version control system. - **The nature of the project (Python, text-based) generally allows for this.**
*   **N/A** It is OPTIONAL for contributors to sign their commits and provide an email address, so that future contributors are able to contact past contributors with questions about their work.

**Require review of contributions:**

*   **?**  All contributions that are accepted or committed to release versions of the codebase MUST be reviewed by another contributor. - **Not explicitly stated in the README but implied in the "Pull Request Process". Should be explicitly enforced.**
*   **?**  Reviews MUST include source, policy, tests and documentation. - **Implied but needs to be explicitly stated in the contribution guidelines.**
*   **?**  Reviewers MUST provide feedback on all decisions to not accept a contribution. - **Good practice, but not explicitly stated in the README.**
*   **?**  The review process SHOULD confirm that a contribution conforms to the standards, architecture and decisions set out in the codebase in order to pass review. - **Implied in the "Contribution Guidelines" but should be made more explicit.**
*   **?**  Reviews SHOULD include running both the software and the tests of the codebase. - **Implied by the testing guidelines but should be explicitly stated.**
*   **?**  Contributions SHOULD be reviewed by someone in a different context than the contributor. - **Best practice, but not enforced by GitHub. Might be difficult to achieve early in the project.**
*   **?**  Version control systems SHOULD NOT accept non-reviewed contributions in release versions. - **Cannot be enforced directly on GitHub without specific branch protection rules. Needs to be documented as a process.**
*   **?**  Reviews SHOULD happen within two business days. - **Ambitious for a new open-source project. Might be a goal, but likely not enforced initially.**
*   **N/A** Performing reviews by multiple reviewers is OPTIONAL.

**Document codebase objectives:**

*   **✓**  The codebase MUST contain documentation of its objectives, like a mission and goal statement, that is understandable by developers and designers so that they can use or contribute to the codebase. - **The "Introduction" and "Features" sections provide this.**
*   **?**  Codebase documentation SHOULD clearly describe the connections between policy objectives and codebase objectives. - **Partially covered in the "Introduction" but could be more explicit.**
*   **N/A** Documenting the objectives of the codebase for the general public is OPTIONAL.

**Document the code:**

*   **?**  All of the functionality of the codebase, policy as well as source code, MUST be described in language clearly understandable for those that understand the purpose of the codebase. - **Cannot be fully determined without a thorough code and documentation review.**
*   **✓**  The documentation of the codebase MUST contain a description of how to install and run the software. - **The README provides installation instructions.**
*   **N/A**  The documentation of the codebase MUST contain examples demonstrating the key functionality. **This is an application, not a library.**
*   **?**  The documentation of the codebase SHOULD contain a high level description that is clearly understandable for a wide audience of stakeholders, like the general public and journalists. - **The "Introduction" section provides a good overview but might need further simplification for a non-technical audience.**
*   **✓**  The documentation of the codebase SHOULD contain a section describing how to install and run a standalone version of the source code, including, if necessary, a test dataset. - **The current instructions seem sufficient.**
*   **?**  The documentation of the codebase SHOULD contain examples for all functionality. - **TODO.**
*   **?**  The documentation SHOULD describe the key components or modules of the codebase and their relationships, for example as a high level architectural diagram. - **The "Architecture" section provides a basic overview, but a diagram would be beneficial.**
*   **x**  There SHOULD be continuous integration tests for the quality of the documentation. - **TODO.**
*   **N/A** Including examples that make users want to immediately start using the codebase in the documentation of the codebase is OPTIONAL.

**Use plain English:**

*   **✓**  The set of authoritative languages for codebase documentation MUST be documented. - **Implicitly English, but should be explicitly stated.**
*   **✓**  English MUST be one of the authoritative languages. - **The README is in English.**
*   **✓**  All codebase documentation MUST be up to date in all authoritative languages. - **Currently only English, so this is trivially true.**
*   **✓**  All source code MUST be in English, except where policy is machine interpreted as code. - **Likely true based on the tech stack and standard practices, but needs code review to confirm.**
*   **?**  All bundled policy MUST be available, or have a summary, in all authoritative languages. - **Needs clarification on how the policy is documented.**
*   **?**  There SHOULD be no acronyms, abbreviations, puns or legal/language/domain specific terms in the codebase without an explanation preceding it or a link to an explanation. - **Generally adhered to in the README, but a full review is needed.**
*   **?**  Documentation SHOULD aim for a lower secondary education reading level, as recommended by the Web Content Accessibility Guidelines 2. - **The current README is relatively easy to understand, but a full assessment against WCAG 2 is needed.**
*   **N/A** Providing additional courtesy translations of any code, documentation or tests is OPTIONAL.

**Use open standards:**

*   **✓**  For features of the codebase that facilitate the exchange of data the codebase MUST use an open standard that meets the Open Source Initiative Open Standard Requirements. - **They do.**
*   **✓**  Any non-open standards used MUST be recorded clearly as such in the documentation. - **The project is committed to using open standards.**
*   **✓**  Any standard chosen for use within the codebase MUST be listed in the documentation with a link to where it is available. - **Cf. the "STANDARDS.md" note.**
*   **N/A**  Any non-open standards chosen for use within the codebase MUST NOT hinder collaboration and reuse.
*   **N/A**  If no existing open standard is available, effort SHOULD be put into developing one.
*   **✓**  Open standards that are machine testable SHOULD be preferred over open standards that are not.
*   **N/A**  Non-open standards that are machine testable SHOULD be preferred over non-open standards that are not.

**Use continuous integration:**

*   **x**  All functionality in the source code MUST have automated tests. - **The testing section indicates a strong emphasis on testing, but we are far from full.**
*   **✓**  Contributions MUST pass all automated tests before they are admitted into the codebase. - **Implied but not explicitly stated. `make test` suggests this.**
*   **?**  The codebase MUST have guidelines explaining how to structure contributions. - **The "Contribution Guidelines" section covers this partially but could be more detailed.**
*   **?**  The codebase MUST have active contributors who can review contributions. - **Likely true for the core team, but the project is new.**
*   **?**  Automated test results for contributions SHOULD be public. - **Needs investigation of CI setup and whether it's integrated with GitHub PRs.**
*   **✓**  The codebase guidelines SHOULD state that each contribution should focus on a single issue. - **Implied in the "Contribution Guidelines".**
*   **?**  Source code test and documentation coverage SHOULD be monitored. - **`make test-with-coverage` suggests this is in place, but the extent and enforcement are unclear.**
*   **N/A** Testing policy and documentation for consistency with the source and vice versa is OPTIONAL.
*   **N/A** Testing policy and documentation for style and broken links is OPTIONAL.
*   **N/A** Testing the software by using examples in the documentation is OPTIONAL.

**Publish with an open license:**

*   **✓**  All source code and documentation MUST be licensed such that it may be freely reusable, changeable and redistributable. - **The project is licensed under AGPL-3.0, which fulfills this.**
*   **✓**  Software source code MUST be licensed under an OSI-approved or FSF Free/Libre license. - **AGPL-3.0 is an OSI-approved and FSF Free/Libre license.**
*   **✓**  All source code MUST be published with a license file. - **The project has a `LICENSE` file.**
*   **✓**  Contributors MUST NOT be required to transfer copyright of their contributions to the codebase. - **The AGPL-3.0 license does not require this.**
*   **✓**  All source code files in the codebase SHOULD include a copyright notice and a license header that are machine-readable. - **The REUSE summary indicates this is true.**
*   **N/A** Having multiple licenses for different types of source code and documentation is OPTIONAL.

**Make the codebase findable:**

*   **✓**  The name of the codebase SHOULD be descriptive and free from acronyms, abbreviations, puns or organizational branding.
*   **✓**  The codebase SHOULD have a short description that helps someone understand what the codebase is for or what it does. - **The first paragraph of the README provides this.**
*   **?**  Maintainers SHOULD submit the codebase to relevant software catalogs.
*   **?**  The codebase SHOULD have a website which describes the problem the codebase solves using the preferred jargon of different potential users of the codebase (including technologists, policy experts and managers). - **The README serves as a basic website, and the eventual platform aipress24.com is intended for this. A dedicated documentation website will be provided later.**
*   **?**  The codebase SHOULD be findable using a search engine by codebase name. - **Likely true, given it's on GitHub and the name is relatively unique.**
*   **?**  The codebase SHOULD be findable using a search engine by describing the problem it solves in natural language. - **Needs to be tested with relevant search queries.**
*   **✓**  The codebase SHOULD have a unique and persistent identifier where the entry mentions the major contributors, repository location and website. - **The GitHub URL could be considered a persistent identifier, but a DOI (Digital Object Identifier) might be beneficial for long-term stability.**
*   **✓**  The codebase SHOULD include a machine-readable metadata description, for example in a `publiccode.yml` file. - **It does.**
*   **N/A** A dedicated domain name for the codebase is OPTIONAL.
*   **N/A** Regular presentations at conferences by the community are OPTIONAL.

**Use a coherent style:**

*   **✓**  The codebase MUST use a coding or writing style guide, either the codebase community's own or an existing one referred to in the codebase. - **The "Code Style" section mentions PEP 8, Black, Ruff, and isort, which implies a style guide. However, a dedicated style guide document might be beneficial.**
*   **✓**  Contributions SHOULD pass automated tests on style. - **Style checks are run in the CI chain.**
*   **?**  The style guide SHOULD include expectations for inline comments and documentation for non-trivial sections. - **TODO.**
*   **N/A** Including expectations for understandable English in the style guide is OPTIONAL.

**Document codebase maturity:**

*   **✓**  The codebase MUST be versioned.
*   **✓**  The codebase MUST prominently document whether or not there are versions of the codebase that are ready to use.
*   **N/A**  Codebase versions that are ready to use MUST only depend on versions of other codebases that are also ready to use.
*   **✓**  The codebase SHOULD contain a log of changes from version to version, for example in the `CHANGELOG`.
*   **?**  The method for assigning version identifiers SHOULD be documented. - **Not documented in the README.** TODO.
*   **N/A** It is OPTIONAL to use semantic versioning.

**Summary:**

Aipress24 shows a strong commitment to many principles of the Standard for Public Code, especially in its openness, detailed roadmap, and thorough contribution guidelines. However, there are several areas where it needs improvement or further clarification to fully comply:

**Key Areas Needing Attention:**

1. **Policy Documentation:** Clearly define and document the project's policy, and ensure it's bundled with the codebase.
2. **Security Reporting:** Establish a clear process for responsible disclosure of security vulnerabilities.
3. **Governance:** Create a `GOVERNANCE` file to document the project's governance model.
4. **Code Review Process:** Explicitly state the code review requirements in the contribution guidelines.
5. **Standards Usage:** Document the specific open standards used and how they are implemented.
6. **Versioning and Maturity:** Clearly document the versioning scheme and the maturity level of different versions.

**Overall Assessment:**

Aipress24 is on the right track but needs more work to fully adhere to the Standard for Public Code. Based on the current information, it's **partially compliant**. The project demonstrates a good understanding of many principles but needs to address the identified gaps to achieve full compliance. The detailed roadmap suggests that many of these issues are planned to be addressed in the future.
