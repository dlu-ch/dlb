# You can set these variables from the command line.
SPHINXBUILD = sphinx-build

# User-friendly check for sphinx-build
ifeq ($(shell which $(SPHINXBUILD) >/dev/null 2>&1; echo $$?), 1)
$(error The '$(SPHINXBUILD)' command was not found. Make sure you have Sphinx installed, then set the SPHINXBUILD environment variable to point to the full path of the '$(SPHINXBUILD)' executable. Alternatively you can add the directory with the executable to your PATH. If you don't have Sphinx installed, grab it from http://sphinx-doc.org/)
endif

.PHONY: all
all: sphinx-html sphinx-linkcheck test

.PHONY: test
test:
	cd ./test && python3 test_path.py
	cd ./test && python3 test_tokentemplate.py

.PHONY: sphinx-html
html:
	cd ./doc/ && $(SPHINXBUILD) -b html -d ../out/sphinx/doctrees . ../out/sphinx/html

.PHONY: sphinx-linkcheck
sphinx-linkcheck:
	cd ./doc/ && $(SPHINXBUILD) -b linkcheck -d ../out/sphinx/doctrees . ../out/sphinx/linkcheck

.PHONY: clean
clean:
	rm -rf -- ./out/
