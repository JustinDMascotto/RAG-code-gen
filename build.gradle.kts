plugins {
    kotlin("jvm") version "1.9.23"
}

group = "com.w2g"
version = "1.0-SNAPSHOT"

repositories {
    maven("https://jitpack.io")
    mavenCentral()
}

dependencies {
    implementation("com.github.kotlinx.ast:grammar-kotlin-parser-antlr-kotlin:0.1.0")

    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}
kotlin {
    jvmToolchain(17)
}