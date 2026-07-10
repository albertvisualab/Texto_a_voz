
import re
import sys
import os

# Añadir el directorio actual al path
sys.path.append(os.getcwd())

from processor import TextProcessor

def test_chunking_repetition():
    text = " ".join([f"Oración número {i}." for i in range(1, 100)])
    # Forzar chunks pequeños para que se divida mucho
    chunks = TextProcessor.split_into_chunks(text, target_len=100, first_chunk_len=100)
    
    print(f"Total chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i}: {chunk[:50]}...")
        
    # Verificar si hay texto repetido en chunks consecutivos
    for i in range(len(chunks) - 1):
        if chunks[i] in chunks[i+1] or chunks[i+1] in chunks[i]:
            print(f"ALERTA: Posible solapamiento entre chunk {i} y {i+1}")
            return False
            
    print("Prueba de solapamiento superada.")
    return True

if __name__ == "__main__":
    test_chunking_repetition()
