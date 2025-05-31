package com.breeze

import kotlinx.ast.common.AstSource
import kotlinx.ast.common.ast.Ast
import kotlinx.ast.common.ast.AstNode
import kotlinx.ast.common.ast.DefaultAstNode
import kotlinx.ast.common.ast.DefaultAstTerminal
import kotlinx.ast.grammar.kotlin.target.antlr.kotlin.KotlinGrammarAntlrKotlinParser
import java.util.*

class App

fun main(args: Array<String>) {
    val result = KotlinGrammarAntlrKotlinParser.parseKotlinFile(
        AstSource.File(
        "/Users/justin.mascotto/Projects/organization-service/organization-service-common/src/main/kotlin/com/w2g/organization/common/dao/OrganizationReadProjectionDao.kt"))

    val node = result as DefaultAstNode
    val chunks = mutableListOf<Map<String, Any>>()
    node.extractDeclarations(chunks)
    println(chunks)
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

fun DefaultAstNode.findNestedChild(name: String): Ast? {
    fun recursive(node: AstNode) : Ast? {
        for (n in node.children) {
            if (n.description == name) {
                return n
            } else if(n is DefaultAstNode) {
                return recursive(n)
            }
        }
        return null
    }

    return recursive(this)
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