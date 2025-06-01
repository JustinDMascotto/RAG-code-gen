plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.5.0"
}
rootProject.name = "ASTparser"

include("ast-parser")
include("qdrant-import")

