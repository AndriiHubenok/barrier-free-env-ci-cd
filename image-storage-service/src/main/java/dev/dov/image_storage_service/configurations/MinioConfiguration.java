package dev.dov.image_storage_service.configurations;

import io.minio.MinioClient;
import okhttp3.OkHttpClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.net.InetSocketAddress;
import java.net.Proxy;

@Configuration
public class MinioConfiguration {

    @Bean
    public MinioClient minioClient() {

        Proxy proxy = new Proxy(
                Proxy.Type.HTTP,
                new InetSocketAddress("garage", 9000)
        );

        OkHttpClient httpClient = new OkHttpClient.Builder()
                .proxy(proxy)
                .build();

        return MinioClient.builder()
                .endpoint("http://localhost:9000")
                .credentials("gto543geoDB", "ekFNkpGzh7ZM")
                .httpClient(httpClient)
                .build();
    }
}

