<div align="center">
  <br>
  <a href="">
    <img src="res/github/ollama-telegram-readme-yais.png" alt="ollama telegram logo" width="300" height="300">
  </a>
  <h1>🦙Ollama Telegram Bot [YAIS-NXZ]</h1>
  <p>
    <b>Chatea con tus Modelos de Lenguaje (LLMs) directamente desde Telegram.</b><br>
    Una interfaz de bot potente, eficiente y altamente configurable para Ollama.
  </p>
  <br>
  
  <div align="center">
    
  ![Static Badge](https://img.shields.io/badge/By%3A-YAIS%20LAB-%23FFD700?style=flat&link=https%3A%2F%2Fyaislab.org)
  ![GitHub stars](https://img.shields.io/github/stars/xnexuzx/ollama-telegram-bot)
  ![GitHub PRs](https://img.shields.io/github/issues-pr/xnexuzx/ollama-telegram-bot)
  ![GitHub forks](https://img.shields.io/github/forks/xnexuzx/ollama-telegram-bot)
  ![GitHub issues](https://img.shields.io/github/issues/xnexuzx/ollama-telegram-bot)
  
  ![Ollama](https://img.shields.io/badge/Ollama-0.12.6-187D87?style=flat&logo=ollama&logoColor=white)
  ![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
  ![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
  ![Batchfile](https://img.shields.io/badge/Scripts-Batchfile-CF4141?style=flat&logo=windows&logoColor=white)
  </div>

  <blockquote>
    <strong>Nota sobre el Origen:</strong> Este es un fork del proyecto original <a href="https://github.com/rikkichy/ollama-telegram">rikkichy/ollama-telegram</a>.
    El código ha sido refactorizado para mejorar la modularidad, añadir nuevas funciones y simplificar drásticamente la instalación en principalmente en Windows. Todo el crédito por el codigo base pertenece a <strong>rikkichy</strong>.
  </blockquote>
</div>

## 🚀 Instalación Rapida (Windows)

La instalación ha sido completamente simplificada con un script Setup interactivo. No necesitas conocimientos técnicos avanzados.

### Pre-requisitos

-   **Ollama**: Asegúrate de tener [Ollama](https://ollama.com/) instalado y ejecutándose.
-   **Python**: Instala [Python 3.8+](https://www.python.org/downloads/) y, durante la instalación, **asegúrate de marcar la opción "Add Python to PATH"**.
-   **Git**: Clona el repositorio usando [Git](https://git-scm.com/downloads).

### Pasos de Instalación

1.  **Clona el repositorio:**

    ```bash
    git clone https://github.com/xnexuzx/ollama-telegram-bot
    cd ollama-telegram-bot
    ```

    _(Reemplaza `xnexuzx` con tu nombre de usuario de GitHub si hiciste Fork)._

2.  **Ejecuta el script de configuración interactivo:**
    Haz doble clic en `Setup.bat`. Una ventana de la consola se abrirá y te guiará a través de todo el proceso:

    -   **Creará un entorno virtual** (`venv`) si no existe.
    -   **Instalará todas las dependencias** de Python desde `requirements.txt`.
    -   **Te hará 4 preguntas sencillas** para generar tu archivo `.env`:
        -   Token de tu bot de Telegram (obtenido de [@BotFather](https://t.me/BotFather)).
        -   Tu ID de usuario de Telegram (obtenido de [@userinfobot](https://t.me/userinfobot)).
        -   URL de tu servidor Ollama (por defecto: `localhost`).
        -   Modelo de Ollama por predeterminado al iniciar (por defecto: `qwen3:4b-instruct`).

3.  **Inicia el bot:**
    Una vez que `Setup.bat` termine, haz doble clic en `start.bat`. El bot se iniciará en segundo plano de forma silenciosa.

4.  **Detén el bot:**
    Para detener el bot, simplemente ejecuta `stop.bat`.

¡Listo! El bot está funcionando y listo para usar.

---

## ✨ Características Principales

-   **Instalación Guiada**: Scripts interactivos que te configuran todo el entorno en minutos.
-   **Manejo Avanzado de Mensajes**:
    -   **Streaming de Respuestas**: Simula una generacion en tiempo real editando los mensajes a medida que se generan.
    -   **División de Mensajes**: Divide automáticamente las respuestas largas.
-   **Eficiente y de Bajos Recursos**:
    -   Optimizado con **Long Polling** para un consumo mínimo de CPU y red.
    -   Gestión de timeouts robusta para prevenir conexiones colgadas.
-   **Gestión de Chats Completa**:
    -   **Múltiples Chats**: Administra varias conversaciones independientes.
    -   **Chats Persistentes y Temporales**: Elige entre guardar una conversación o tener un chat rápido y temporal.
-   **Administración y Seguridad**:
    -   **Gestión de Modelos**: Administra modelos de Ollama (`pull`, `rm`) directamente desde la interfaz del bot.
    -   **Control de Acceso**: Asegura tu bot con una lista blanca (`allowlist`) gestionada por los administradores.
-   **Personalización Avanzada**:
    -   **Prompts de Sistema**: Personaliza la personalidad del bot. Los administradores pueden crear prompts y los usuarios pueden elegir entre ellas.
-   **Soporte para Grupos**: Menciona al bot en un grupo para que responda.

---

## 👨‍💻 Comandos del Bot

### Comandos para Todos los Usuarios (Autorizados)

-   `/start`: Muestra el mensaje de bienvenida.
-   `/prompts`: Permite seleccionar un "system prompt" para cambiar la personalidad del bot. La selección de prompts personalizados es persistente.
-   `/chats`: Abre el menú para gestionar tus conversaciones (crear, cambiar, eliminar).
-   `/reset`: Limpia el historial de la conversación actual, volviéndola un chat temporal.
-   `/history`: Muestra el historial de la conversación activa.

### Comandos de Administrador

Los administradores (definidos en `ADMIN_IDS`) tienen acceso a comandos adicionales para gestionar el bot:

-   `/settings`: Abre el menú principal de ajustes de administrador.
-   `/adduser <user_id> [user_name]`: Añade un usuario a la lista de permitidos.
-   `/rmuser <user_id>`: Elimina un usuario de la lista de permitidos.
-   `/listusers`: Muestra todos los usuarios autorizados.
-   `/pullmodel <model_name>`: Descarga un modelo desde el registro de Ollama.

### Menú de Ajustes de Administrador (`/settings`)

Desde este menú, los administradores pueden:

-   **Cambiar el LLM activo**: Seleccionar qué modelo de Ollama usar.
-   **Eliminar un LLM**: Borrar un modelo del servidor de Ollama.
-   **Administrar Prompts**: Crear, ver y eliminar los prompts de sistema personalizados que todos los usuarios podrán seleccionar.
-   **Listar y Eliminar Usuarios**: Ver la lista de usuarios autorizados y eliminarlos directamente desde un menú interactivo.

---

## ⚙️ Configuración de Variables de Entorno (`.env`)

| Parámetro         | Descripción                                                                                | Requerido |  Valor por Defecto  | Ejemplo                |
| ----------------- | ------------------------------------------------------------------------------------------ | :-------: | :-----------------: | ---------------------- |
| `TOKEN`           | El token de tu bot de Telegram.                                                            |    Sí     |                     | `123456:ABC-DEF123456` |
| `ADMIN_IDS`       | ID numérico del usuario administrador.                                                     |    Sí     |                     | `123456789`            |
| `INITMODEL`       | El modelo de Ollama que se cargará por defecto al iniciar el bot.                          |    No     | `qwen3:4b-instruct` | `mistral:latest`       |
| `OLLAMA_BASE_URL` | La URL o IP de tu servidor Ollama. Si está en la misma máquina, `localhost` es suficiente. |    No     |     `localhost`     | `192.168.1.100`        |
| `OLLAMA_PORT`     | El puerto de tu servidor Ollama.                                                           |    No     |       `11434`       | `11434`                |
| `TIMEOUT`         | Tiempo máximo en segundos para esperar una respuesta de Ollama.                            |    No     |       `3000`        | `3000`                 |
| `LOG_LEVEL`       | Nivel de logging del bot.                                                                  |    No     |       `INFO`        | `INFO`                 |

---

## 🐳 Instalación con Docker (Avanzado)

_Próximamente..._

---

## 📄 Licencia

Este proyecto está bajo la Licencia [MIT](LICENSE). Consulta el archivo `LICENSE` para más detalles.
