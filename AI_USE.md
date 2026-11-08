# AI Use Declaration

AI assistance was used while developing this project. Claude Code assisted with initial scaffolding and documentation; OpenAI Codex was used for later implementation, debugging, evidence collection, report review, and submission preparation. Ollama `phi3.5` served as the teacher model for the required labelling task.

The coding assistants helped draft and revise Python scripts, tests, Docker and Kubernetes configuration, CI workflows, and documentation. Their output was checked through the supplied scoring and NACL tools, local tests, container and k3d runs, and GitHub Actions. Measured results are retained under `results/`; the report also identifies the load and rollout targets that were missed. Model predictions and measurements are reported from those artifacts, not inferred from assistant suggestions.

AI help did not replace the required teacher or student runs. The teacher generated the raw command labels; the `pythia-70m` student was trained on cleaned labels. Model archives are published as Release assets rather than committed to Git. The handwritten reflection is a separate scanned submission artifact.

Known limitations include a 50% full-frame score for student v1, three failed requests in the 254-request standard load run, and six failed requests in the 238-request rollout run. The report discusses these results and possible improvements.
