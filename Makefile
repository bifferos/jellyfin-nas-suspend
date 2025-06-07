.PHONY: run clean install uninstall


APP_NAME := jellyfin-nas-suspend

BINARY_NAME := $(APP_NAME).py
INSTALL_DIR := /usr/local/bin
SERVICE_FILE := $(APP_NAME).service
SYSTEMD_DIR := /etc/systemd/system

USR_SHARE := /usr/share/$(APP_NAME)


run:
	./$(BINARY_NAME) --config config.json


install:
	sudo install -m 755 $(BINARY_NAME) $(INSTALL_DIR)/
	sudo install -m 644 $(SERVICE_FILE) $(SYSTEMD_DIR)/
	sudo systemctl daemon-reexec
	sudo systemctl enable --now $(SERVICE_FILE)
	@echo "Installed and started $(SERVICE_FILE)"


uninstall:
	sudo systemctl disable --now $(APP_NAME).service
	sudo rm -f $(INSTALL_DIR)/$(BINARY_NAME)
	sudo rm -f $(SYSTEMD_DIR)/$(SERVICE_FILE)
	sudo systemctl daemon-reexec
	@echo "Stopped and uninstalled $(SERVICE_FILE)"


clean:
	rm *~

