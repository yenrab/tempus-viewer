# Shared by the leaf Makefiles of testnet/nodes. TEST network only.
# Needs BEES_ROOT (a clone of project-bees, natives built with `make -C native tls` then `make -C native tempus`) and
# SILICA_ROOT (a Silica checkout: the release compiler carries no standard library units, so their sources come from
# here), and SILICA_COMPILER (the release binary) on the command line or in the environment.
ifndef BEES_ROOT
$(error set BEES_ROOT to the project-bees clone)
endif
ifndef SILICA_ROOT
$(error set SILICA_ROOT to the Silica checkout (compiler/stdlib/*.silica))
endif
ifndef SILICA_COMPILER
$(error set SILICA_COMPILER to the release compiler binary)
endif
# BEES's tools/silica.mk takes SILICA_COMPILER only from the make command line (from the environment it falls back to the
# Silica checkout's binaries/silica-compiler, a different compiler): so it must be on the command line, as build.sh does
ifneq ($(origin SILICA_COMPILER),command line)
$(error pass SILICA_COMPILER=... on the make command line (build.sh does); the environment is ignored by BEES's silica.mk)
endif
export BEES_ROOT SILICA_ROOT
TESTNET := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
CERTS_TRUST := $(BEES_ROOT)/trials/n4_trust_tls/certs
CERTS_TEMPUS := $(BEES_ROOT)/trials/t5_tempus_tls/certs
# the units a TRUST node's lib/ links to (BEES's src/trust and the Silica standard library), as the trials do with
# tracked symbolic links; here they are made by `make links`, from BEES_ROOT and SILICA_ROOT, and ignored by git
LNK_TRUST := bees_trust_frame.silica bees_trust_guard.silica bees_trust_work.silica bees_trust.atoms \
  dangerous_bees_tls_native.silica dangerous_bees_tls.silica dangerous_bees_trust_edge.silica \
  dangerous_bees_trust_native.silica dangerous_bees_trust.silica
LNK_TEMPUS := bees_tempus_admit.silica bees_tempus_bridge.silica bees_tempus_frame.silica bees_tempus_store_actor.silica \
  bees_tempus_store.silica bees_tempus_view.silica bees_tempus.atoms dangerous_bees_tempus_conn.silica \
  dangerous_bees_tempus_draws.silica dangerous_bees_tempus_edge.silica dangerous_bees_tempus_native.silica \
  dangerous_bees_tempus_tls.silica
LNK_TEMPUS_TEST := bees_tempus_test.atoms bees_tempus_test.silica
LNK_STD := wire_etf.silica wireframe.silica dangerous_sockets.silica dangerous_tcp_carrier.silica
define LINKS
	mkdir -p lib && cd lib && \
	for f in $(LNK_TRUST); do ln -sfn "$(BEES_ROOT)/src/trust/$$f" "$$f"; done && \
	for f in $(LNK_STD); do ln -sfn "$(SILICA_ROOT)/compiler/stdlib/$$f" "$$f"; done && \
	ln -sfn "$(SILICA_ROOT)/compiler/stdlib/Carrier.silica" carrier.silica && \
	ln -sfn "$(BEES_ROOT)/native/dangerous_exposure_source" ../dangerous_exposure_source && cd ..
endef
define LINKS_TEMPUS
	cd lib && \
	for f in $(LNK_TEMPUS); do ln -sfn "$(BEES_ROOT)/src/tempus/$$f" "$$f"; done && \
	for f in $(LNK_TEMPUS_TEST); do ln -sfn "$(BEES_ROOT)/src/tempus_test/$$f" "$$f"; done
endef
