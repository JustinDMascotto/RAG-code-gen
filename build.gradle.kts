plugins {
    kotlin("jvm") version "1.9.23"
}

group = "com.breeze"
version = "1.0-SNAPSHOT"

allprojects {
    repositories {
        maven("https://jitpack.io")
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "org.jetbrains.kotlin.jvm")
    
    tasks.withType<Test> {
        useJUnitPlatform()
    }
    
    kotlin {
        jvmToolchain(17)
    }
}