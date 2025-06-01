package com.breeze

import kotlinx.ast.common.AstSource
import kotlinx.ast.common.ast.Ast
import kotlinx.ast.common.ast.DefaultAstNode
import kotlinx.ast.common.ast.DefaultAstTerminal
import kotlinx.ast.grammar.kotlin.target.antlr.kotlin.KotlinGrammarAntlrKotlinParser
import java.io.File
import java.util.*
import kotlin.system.exitProcess

fun main(args: Array<String>) {
    if (args.isEmpty()) {
        println("Usage: java -jar astparser.jar [--output=jsonl|json|summary] <file1.kt> <file2.kts> <directory1> ...")
        println("Processes Kotlin (.kt) and Kotlin Script (.kts) files")
        println("Output formats:")
        println("  --output=jsonl   Output JSONL for streaming to Qdrant (default for automation)")
        println("  --output=json    Output structured JSON")
        println("  --output=summary Human-readable summary (default)")
        exitProcess(1)
    }

    var outputFormat = "summary"
    val paths = mutableListOf<String>()
    
    for (arg in args) {
        when {
            arg.startsWith("--output=") -> {
                outputFormat = arg.substringAfter("--output=")
            }
            else -> paths.add(arg)
        }
    }
    
    val kotlinFiles = mutableListOf<File>()
    
    for (path in paths) {
        val file = File(path)
        if (!file.exists()) {
            System.err.println("Warning: '$path' does not exist, skipping...")
            continue
        }
        
        when {
            file.isFile && file.extension in listOf("kt", "kts") -> {
                kotlinFiles.add(file)
            }
            file.isDirectory -> {
                kotlinFiles.addAll(findKotlinFiles(file))
            }
            else -> {
                System.err.println("Warning: '$path' is not a Kotlin file or directory, skipping...")
            }
        }
    }
    
    if (kotlinFiles.isEmpty()) {
        System.err.println("No Kotlin files found to process")
        exitProcess(1)
    }
    
    if (outputFormat == "summary") {
        System.err.println("Processing ${kotlinFiles.size} Kotlin files...")
    }
    
    for (kotlinFile in kotlinFiles) {
        try {
            if (outputFormat == "summary") {
                System.err.println("\n=== Processing: ${kotlinFile.absolutePath} ===")
            }
            processKotlinFile(kotlinFile, outputFormat)
        } catch (e: Exception) {
            System.err.println("Error processing ${kotlinFile.absolutePath}: ${e.message}")
        }
    }
}

fun findKotlinFiles(directory: File): List<File> {
    return directory.walkTopDown()
        .filter { it.isFile && it.extension in listOf("kt", "kts") }
        .toList()
}

fun processKotlinFile(file: File, outputFormat: String = "summary") {
    val result = KotlinGrammarAntlrKotlinParser.parseKotlinFile(AstSource.File(file.absolutePath))
    val node = result as DefaultAstNode
    val chunks = mutableListOf<Map<String, Any>>()
    node.extractDeclarations(chunks)
    
    when (outputFormat) {
        "jsonl" -> {
            chunks.forEach { chunk ->
                val qdrantPayload = mapOf(
                    "id" to chunk["id"],
                    "file_path" to file.absolutePath,
                    "symbol" to chunk["symbol"],
                    "kind" to chunk["kind"],
                    "code" to chunk["code"],
                    "metadata" to chunk["metadata"]
                )
                println(com.fasterxml.jackson.module.kotlin.jacksonObjectMapper().writeValueAsString(qdrantPayload))
            }
        }
        "json" -> {
            val output = mapOf(
                "file_path" to file.absolutePath,
                "declarations" to chunks
            )
            println(com.fasterxml.jackson.module.kotlin.jacksonObjectMapper().writeValueAsString(output))
        }
        else -> {
            if (chunks.isNotEmpty()) {
                println("Found ${chunks.size} declarations:")
                chunks.forEach { chunk ->
                    println("  - ${chunk["kind"]}: ${chunk["symbol"]}")
                }
            } else {
                println("No declarations found")
            }
        }
    }
}

fun DefaultAstNode.extractDeclarations(chunks: MutableList<Map<String, Any>>, parentClass: String? = null) {
    when (this.description) {
        "functionDeclaration" -> {
            val name = findChild("simpleIdentifier")?.text()
            val modifiers = findChildren("modifier")?.mapNotNull { it.text() }
            val annotations = findChildren("annotation")?.mapNotNull { it.text() }

            val codeText = flattenCode()
            val chunk = mapOf(
                "id" to UUID.randomUUID().toString(),
                "symbol" to listOfNotNull(parentClass, name).joinToString("."),
                "kind" to "function",
                "code" to codeText,
                "metadata" to mapOf(
                    "modifiers" to modifiers,
                    "annotations" to annotations,
                    "parent" to parentClass
                )
            )
            chunks.add(chunk)
        }

        "classDeclaration" -> {
            val className = findChild("simpleIdentifier")?.text() ?: "UnnamedClass"
            val codeText = flattenCode()
            val classChunk = mapOf(
                "id" to UUID.randomUUID().toString(),
                "symbol" to className,
                "kind" to "class",
                "code" to codeText,
                "metadata" to mapOf(
                    "parent" to parentClass
                )
            )
            chunks.add(classChunk)

            children.filterIsInstance<DefaultAstNode>().forEach {
                it.extractDeclarations(chunks, parentClass = className)
            }
        }

        else -> {
            children.filterIsInstance<DefaultAstNode>().forEach {
                it.extractDeclarations(chunks, parentClass)
            }
        }
    }
}



fun DefaultAstNode.findChild(name: String): DefaultAstNode? =
    this.children.filterIsInstance<DefaultAstNode>().firstOrNull {
        it.description == name
    }

fun DefaultAstNode.findChildren(name: String): List<DefaultAstNode>? =
    this.children.filterIsInstance<DefaultAstNode>().filter {
        it.description == name
    }

fun DefaultAstNode.text(): String? =
    this.children.filterIsInstance<DefaultAstTerminal>().joinToString("") { it.text }

fun DefaultAstNode.flattenCode(): String =
    buildString {
        appendAllTokens( this, this@flattenCode)
    }

fun appendAllTokens(sb: StringBuilder, node: Ast) {
    when (node) {
        is DefaultAstTerminal -> sb.append(node.text)
        is DefaultAstNode -> node.children.forEach { appendAllTokens(sb, it) }
    }
}