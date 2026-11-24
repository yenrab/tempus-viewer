# The reply check: one program (no network) that runs the content node's generated MFA entry for viewer:home/0 and prints the
# reply's bytes. Its lib/ is the content node's generated units (build nodes/content first).
LEAF_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
include $(LEAF_DIR)/../common.mk
CONTENT := $(TESTNET)/nodes/content/lib
LIBS := carrier.silica wireframe.silica rep_content.silica rep_content.atoms rep_images.silica rep_images.atoms node_names.atoms bees_trust_mfa.silica bees_trust_mfa.atoms bees_trust_conf.atoms wire_etf.silica
# the links are made when this file is read, because trial.mk lists lib/*.atoms then (make 3.81 lists a directory once)
_ := $(shell mkdir -p "$(LEAF_DIR)/lib" && cd "$(LEAF_DIR)/lib" && for f in $(LIBS); do ln -sfn "$(CONTENT)/$$f" "$$f"; done && ln -sfn "$(BEES_ROOT)/src/trust/bees_trust.atoms" bees_trust.atoms && ln -sfn "$(BEES_ROOT)/src/trust/bees_trust_frame.silica" bees_trust_frame.silica && cd "$(LEAF_DIR)" && ln -sfn "$(BEES_ROOT)/native/dangerous_exposure_source" dangerous_exposure_source)
include $(BEES_ROOT)/tools/trial.mk
GENERATED := $(wildcard $(LEAF_DIR)/lib/* $(LEAF_DIR)/*.sams $(LEAF_DIR)/*.iface $(LEAF_DIR)/*.o $(LEAF_DIR)/replycheck $(LEAF_DIR)/silica.* $(LEAF_DIR)/dangerous_exposure_source)
clean-generated:
	@rm -f $(GENERATED)
