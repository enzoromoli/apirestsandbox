# sandboxd — commandes du TP. Prérequis : Node 22+ (npx), Python 3.11+, Docker.
SPEC          ?= openapi.yaml
PORT          ?= 8000
DOCKER_SOCKET ?= /var/run/docker.sock
VENV          ?= .venv

.PHONY: help lint mock docs install run test-contract flaky clean

help:
	@echo "make lint           vérifier le contrat (Spectral)"
	@echo "make mock           simuler l'API à partir du contrat (Prism, port 4010)"
	@echo "make docs           générer la documentation HTML (docs.html)"
	@echo "make install        installer les dépendances Python"
	@echo "make run            lancer sandboxd (port $(PORT))"
	@echo "make test-contract  rejouer le contrat contre sandboxd (Schemathesis)"
	@echo "make flaky          lancer l'API d'entraînement capricieuse (TP4, port 8001)"
	@echo "make clean          supprimer les conteneurs créés par sandboxd"

lint:
	npx -y @stoplight/spectral-cli@6.17.0 lint $(SPEC) --ruleset .spectral.yaml

mock:
	npx -y @stoplight/prism-cli@5.16.0 mock $(SPEC) -p 4010

docs:
	npx -y @redocly/cli@2.71.2 build-docs $(SPEC) -o docs.html

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -r requirements.txt

run:
	DOCKER_SOCKET=$(DOCKER_SOCKET) $(VENV)/bin/uvicorn app.main:app --reload --port $(PORT)

# positive_data_acceptance est exclu : il considère comme une faute les refus
# légitimes liés à l'état (jeton de page inconnu, If-Match périmé, clé réutilisée).
test-contract:
	$(VENV)/bin/schemathesis run $(SPEC) --url http://localhost:$(PORT) -n 20 -w 1 \
		--exclude-checks positive_data_acceptance

flaky:
	$(VENV)/bin/uvicorn training.flaky_api:app --port 8001

clean:
	docker ps -aq --filter label=sandboxd=1 | xargs -r docker rm -f
