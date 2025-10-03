# Bot Discord em Python

Este projeto transforma seu servidor em um chatbot alimentado por IA usando a API do [OpenRouter](https://openrouter.ai/). É construído sobre o [discordpy](https://discordpy.readthedocs.io/); leia [seus guias de primeiros passos](https://discordpy.readthedocs.io/en/stable/#getting-started) para aproveitar ao máximo este template.

## Começando

Para configurar, você precisa seguir [estas instruções de configuração da conta do bot](https://discordpy.readthedocs.io/en/stable/discord.html), e então copiar o token do seu bot e adicioná-lo como um segredo com a chave `TOKEN` no painel "Secrets (Environment variables)".

## Configurando o OpenRouter

1. Crie uma conta no [OpenRouter](https://openrouter.ai/) e gere uma chave de API.
2. Cadastre as seguintes variáveis de ambiente:
   - `OPENROUTER_API_KEY`: **obrigatória**. Chave de API gerada no painel do OpenRouter.
   - `OPENROUTER_MODEL`: opcional. Nome do modelo a ser utilizado (padrão `openrouter/auto`).
   - `OPENROUTER_SYSTEM_PROMPT`: opcional. Texto usado como instrução inicial para o assistente.
   - `OPENROUTER_TIMEOUT`: opcional. Tempo limite (em segundos) para aguardar a resposta da API; padrão `60`.
   - `OPENROUTER_MAX_TURNS`: opcional. Número de trocas de mensagens mantidas no histórico por canal; padrão `6`.
   - `OPENROUTER_REFERER` e `OPENROUTER_TITLE`: opcionais, informam o domínio e nome do app conforme recomenda a documentação do OpenRouter.
3. Execute o bot normalmente. Ele responderá automaticamente a mensagens diretas, menções e respostas aos próprios envios.

## FAQ

Se você receber a seguinte mensagem de erro ao tentar iniciar o servidor: `429 Too Many Requests` (acompanhado por muito código HTML), tente o conselho dado nesta pergunta do Stackoverflow: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests

## Sistema RAG (Retrieval-Augmented Generation)

O bot agora suporta um sistema RAG avançado que permite respostas contextuais baseadas em documentos jurídicos. O sistema processa documentos legais (leis, jurisprudência, doutrinas) em vários formatos e os utiliza para enriquecer as respostas do chatbot.

### Configuração do Sistema RAG

Para habilitar o sistema RAG, configure as seguintes variáveis de ambiente:

**Variáveis obrigatórias:**
- `RAG_ENABLED`: Defina como `true` para habilitar o sistema RAG.
- `OPENAI_API_KEY`: **obrigatória**. Chave de API do OpenAI para geração de embeddings.

**Variáveis opcionais:**
- `RAG_CHROMA_PATH`: Caminho para persistir o banco de dados ChromaDB (padrão: `./chroma_db`).
- `RAG_COLLECTION_NAME`: Nome da coleção no banco de dados (padrão: `legal_documents`).
- `RAG_MAX_CONTEXT`: Número máximo de tokens para contexto recuperado (padrão: `3000`).
- `RAG_SIMILARITY_THRESHOLD`: Limite de similaridade para recuperação (padrão: `0.7`).
- `RAG_CHUNK_SIZE`: Tamanho dos chunks de texto para embedding (padrão: `1000`).
- `RAG_CHUNK_OVERLAP`: Sobreposição entre chunks (padrão: `200`).

### Como usar o Sistema RAG

1. **Habilite o sistema RAG** definindo `RAG_ENABLED=true` e configure a chave do OpenAI.
2. **Adicione documentos** usando o comando administrativo `/add_document`.
3. **Converse normalmente** - o bot automaticamente buscará contexto relevante de documentos processados.

### Comando Administrativo para Documentos

- `/add_document <attachment>`: Faça upload de um documento legal para o sistema RAG (requer permissão de Administrador).

**Formatos suportados:** PDF, DOCX, DOC, Markdown (.md), TXT.
**Tamanho máximo:** 10MB por arquivo.

O sistema automaticamente:
- Extrai texto dos documentos
- Remove duplicatas baseado no hash do conteúdo
- Divide documentos grandes em chunks menores
- Gera embeddings usando OpenAI
- Armazena no banco de dados vetorial ChromaDB

## Administrative Commands

The bot now supports moderation commands for server management (available as slash commands):

- `/ban <user> [reason]`: Ban a user from the server (requires Ban Members permission).
- `/kick <user> [reason]`: Kick a user from the server (requires Kick Members permission).
- `/mute <user> [duration in minutes] [reason]`: Timeout a user for the specified duration (requires Moderate Members permission).
- `/unmute <user> [reason]`: Remove timeout from a user (requires Moderate Members permission).
- `/warn <user> [reason]`: Issue a warning to a user (requires Kick Members permission).
- `/purge <amount>`: Delete up to 100 messages from the channel (requires Manage Messages permission).
- `/add_document <attachment>`: Upload a legal document to the RAG system (requires Administrator permission).

All moderation actions are logged to `moderation_log.json`, and user warnings are tracked in `warns.json` for administrative reference.
