"""Unit tests are offline; vector integration tests explicitly select Qdrant."""
import os
os.environ['RETRIEVAL_BACKEND'] = 'lexical'
