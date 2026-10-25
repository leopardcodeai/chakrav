idf_component_register(SRCS "main.c" "camera.c"
    PRIV_REQUIRES app_display app_chakra esp_iris esp_mosaico_app_recovery
        esp_mosaico_gsp_bundle esp_mosaico_gsp_iris nvs_flash log
        esp_wifi esp_netif esp_event esp_http_client esp_http_server esp_timer lwip mbedtls esp-mosaico-bsp
        mosaico_module_camera esp_driver_ppa esp_driver_jpeg esp_mm)
