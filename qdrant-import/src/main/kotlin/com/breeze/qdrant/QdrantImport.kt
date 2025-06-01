package com.breeze.qdrant

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.fasterxml.jackson.module.kotlin.readValue
import com.github.ajalt.clikt.core.CliktCommand
import com.github.ajalt.clikt.parameters.options.default
import com.github.ajalt.clikt.parameters.options.option
import com.github.ajalt.clikt.parameters.options.required
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.engine.cio.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.serialization.jackson.*
import kotlinx.coroutines.runBlocking
import java.io.BufferedReader
import java.io.InputStreamReader
import kotlin.system.exitProcess

data class CodeChunk(
    val id: String,
    val file_path: String,
    val symbol: String,
    val kind: String,
    val code: String,
    val metadata: Map<String, Any>
)

data class QdrantPoint(
    val id: String,
    val vector: List<Float>,
    val payload: Map<String, Any>
)

data class QdrantUpsertRequest(
    val points: List<QdrantPoint>
)

class QdrantImportCommand : CliktCommand(name = "qdrant-import") {
    private val qdrantUrl by option("--qdrant-url", help = "Qdrant server URL").default("http://localhost:6333")
    private val collection by option("--collection", help = "Qdrant collection name").required()
    private val batchSize by option("--batch-size", help = "Batch size for uploads").default("100")
    private val embeddingUrl by option("--embedding-url", help = "Embedding service URL (optional)")
    
    private val mapper = jacksonObjectMapper()
    private val client = HttpClient(CIO) {
        install(ContentNegotiation) {
            jackson()
        }
    }

    override fun run() = runBlocking {
        try {
            echo("Starting import to Qdrant collection: $collection")
            echo("Qdrant URL: $qdrantUrl")
            echo("Batch size: $batchSize")
            
            ensureCollectionExists()
            
            val reader = BufferedReader(InputStreamReader(System.`in`))
            val batch = mutableListOf<CodeChunk>()
            var totalProcessed = 0
            
            reader.useLines { lines ->
                for (line in lines) {
                    if (line.isBlank()) continue
                    
                    try {
                        val chunk = mapper.readValue<CodeChunk>(line)
                        batch.add(chunk)
                        
                        if (batch.size >= batchSize.toInt()) {
                            processBatch(batch)
                            totalProcessed += batch.size
                            echo("Processed $totalProcessed items...")
                            batch.clear()
                        }
                    } catch (e: Exception) {
                        echo("Error parsing line: $line", err = true)
                        echo("Error: ${e.message}", err = true)
                    }
                }
            }
            
            // Process remaining items
            if (batch.isNotEmpty()) {
                processBatch(batch)
                totalProcessed += batch.size
            }
            
            echo("Import completed. Total items processed: $totalProcessed")
            
        } catch (e: Exception) {
            echo("Import failed: ${e.message}", err = true)
            exitProcess(1)
        } finally {
            client.close()
        }
    }
    
    private suspend fun ensureCollectionExists() {
        try {
            // Check if collection exists
            val response = client.get("$qdrantUrl/collections/$collection")
            if (response.status == HttpStatusCode.OK) {
                echo("Collection '$collection' exists")
                return
            }
        } catch (e: Exception) {
            // Collection might not exist, try to create it
        }
        
        // Create collection with default vector size (384 for sentence-transformers)
        val createRequest = mapOf(
            "vectors" to mapOf(
                "size" to 384,
                "distance" to "Cosine"
            )
        )
        
        try {
            val response = client.put("$qdrantUrl/collections/$collection") {
                contentType(ContentType.Application.Json)
                setBody(createRequest)
            }
            
            if (response.status.isSuccess()) {
                echo("Created collection '$collection'")
            } else {
                throw Exception("Failed to create collection: ${response.status}")
            }
        } catch (e: Exception) {
            throw Exception("Failed to create collection: ${e.message}")
        }
    }
    
    private suspend fun processBatch(chunks: List<CodeChunk>) {
        val points = chunks.map { chunk ->
            QdrantPoint(
                id = chunk.id,
                vector = generateEmbedding(chunk.code),
                payload = mapOf(
                    "file_path" to chunk.file_path,
                    "symbol" to chunk.symbol,
                    "kind" to chunk.kind,
                    "code" to chunk.code,
                    "metadata" to chunk.metadata
                )
            )
        }
        
        val request = QdrantUpsertRequest(points)
        
        try {
            val response = client.put("$qdrantUrl/collections/$collection/points") {
                contentType(ContentType.Application.Json)
                setBody(request)
            }
            
            if (!response.status.isSuccess()) {
                throw Exception("Qdrant upload failed: ${response.status}")
            }
        } catch (e: Exception) {
            throw Exception("Failed to upload batch: ${e.message}")
        }
    }
    
    private suspend fun generateEmbedding(text: String): List<Float> {
        if (embeddingUrl != null) {
            try {
                val response = client.post("$embeddingUrl/embed") {
                    contentType(ContentType.Application.Json)
                    setBody(mapOf("texts" to listOf(text)))
                }
                
                if (response.status.isSuccess()) {
                    val result: Map<String, Any> = response.body()
                    @Suppress("UNCHECKED_CAST")
                    val embeddings = result["embeddings"] as? List<List<Double>>
                        ?: result["embedding"] as? List<Double>
                        ?: throw Exception("Invalid embedding response format")
                    
                    return if (embeddings is List<*> && embeddings.isNotEmpty() && embeddings[0] is List<*>) {
                        // Handle response like {"embeddings": [[0.1, 0.2, ...]]}
                        (embeddings[0] as List<Double>).map { it.toFloat() }
                    } else {
                        // Handle response like {"embedding": [0.1, 0.2, ...]}
                        (embeddings as List<Double>).map { it.toFloat() }
                    }
                }
            } catch (e: Exception) {
                echo("Warning: Embedding service failed, using random vector $e \n${e.stackTrace}", err = true)
            }
        }
        
        // Fallback: generate random embedding (for testing)
        return (1..384).map { kotlin.random.Random.nextFloat() * 2 - 1 }
    }
}

fun main(args: Array<String>) = QdrantImportCommand().main(args)