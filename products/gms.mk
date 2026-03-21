#
# Copyright (C) 2020 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Default notification/alarm sounds
PRODUCT_PRODUCT_PROPERTIES += \
    ro.config.notification_sound=Popcorn.ogg \
    ro.config.alarm_alert=Bright_morning.ogg

# Default ringtone
PRODUCT_PRODUCT_PROPERTIES += \
    ro.config.ringtone=The_big_adventure.ogg

# Gboard Props
PRODUCT_PRODUCT_PROPERTIES += \
    ro.com.google.ime.bs_theme=true \
    ro.com.google.ime.theme_id=5 \
    ro.com.google.ime.system_lm_dir=/product/usr/share/ime/google/d3_lms

# GMS Props
PRODUCT_PRODUCT_PROPERTIES += \
    ro.opa.eligible_device=true

# Pixel
PRODUCT_PACKAGES += \
    GoogleSettingsOverlay \
    GoogleSystemUIOverlay

# Google Battery
TARGET_DOES_NOT_SUPPORT_GOOGLE_BATTERY ?= true

# Include TurboAdapter without Google Battery support
ifeq ($(TARGET_DOES_NOT_SUPPORT_GOOGLE_BATTERY),true)
PRODUCT_PACKAGES += \
    TurboAdapter_NoBatt
endif

# SetupWizard Props
PRODUCT_PRODUCT_PROPERTIES += \
    ro.setupwizard.enterprise_mode=1 \
    ro.setupwizard.esim_cid_ignore=00000001 \
    setupwizard.feature.baseline_setupwizard_enabled=true \
    setupwizard.feature.day_night_mode_enabled=true \
    setupwizard.feature.portal_notification=true \
    setupwizard.feature.enable_quick_start_flow=true \
    setupwizard.feature.enable_restore_anytime=true \
    setupwizard.feature.enable_wifi_tracker=true \
    setupwizard.feature.lifecycle_refactoring=true \
    setupwizard.feature.notification_refactoring=true \
    setupwizard.feature.show_pai_screen_in_main_flow.carrier1839=false \
    setupwizard.feature.show_pixel_tos=true \
    setupwizard.feature.show_support_link_in_deferred_setup=false \
    setupwizard.feature.skip_button_use_mobile_data.carrier1839=true \
    setupwizard.personal_safety_suw_enabled=true \
    setupwizard.theme=glif_expressive \
    setupwizard.feature.default_locale_enhancement_enabled=true \
    setupwizard.feature.device_info_icon_enabled=true \
    setupwizard.feature.provisioning_profile_mode=true \
    setupwizard.feature.enable_gil= \
    setupwizard.feature.enable_gil_logging=true \
    setupwizard.feature.enable_minors_setup_flow=true \
    setupwizard.feature.enable_parental_notice_activity=true \
    setupwizard.feature.enable_parental_setup=true \
    setupwizard.feature.enhanced_setup_design_metrics=true \
    setupwizard.feature.is_suw_onboarding_contract_enabled=true \
    setupwizard.feature.joined_up_loading=true \
    setupwizard.feature.locale_agnostic_enabled=true

$(call inherit-product, vendor/gms/common/common-vendor.mk)
