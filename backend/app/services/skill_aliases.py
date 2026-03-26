"""Skill name normalization and alias mapping.

Maps common skill name variations to a single canonical form so that
"React.js", "ReactJS", and "React" all match each other during scoring.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical alias table: every value maps to a canonical key.
# All entries are lowercase.  When a skill is looked up, we first strip and
# lowercase it, then check this table; if found we return the canonical form,
# otherwise the original lowercased string is returned unchanged.
# ---------------------------------------------------------------------------

_ALIAS_TABLE: dict[str, str] = {}


def _register(canonical: str, *aliases: str) -> None:
    """Register a canonical skill name and its aliases."""
    canonical_lower = canonical.lower()
    _ALIAS_TABLE[canonical_lower] = canonical_lower
    for alias in aliases:
        _ALIAS_TABLE[alias.lower()] = canonical_lower


# --- JavaScript ecosystem ---
_register("javascript", "js", "ecmascript", "es6", "es2015", "es2016", "es2017", "es2020", "es2021", "es2022")
_register("typescript", "ts")
_register("react", "react.js", "reactjs", "react js")
_register("vue", "vue.js", "vuejs", "vue js", "vue2", "vue3")
_register("angular", "angular.js", "angularjs", "angular js")
_register("next.js", "nextjs", "next js", "next")
_register("nuxt.js", "nuxtjs", "nuxt js", "nuxt")
_register("node.js", "nodejs", "node js", "node")
_register("express.js", "expressjs", "express")
_register("nest.js", "nestjs", "nest")
_register("vite", "vitejs", "vite.js")
_register("webpack", "webpackjs")
_register("jquery", "jquery.js")
_register("svelte", "sveltejs", "svelte.js")
_register("electron", "electron.js", "electronjs")
_register("deno", "deno.js")
_register("bun", "bun.js")
_register("pinia", "vuex")

# --- CSS / UI ---
_register("css", "css3", "cascading style sheets")
_register("html", "html5")
_register("sass", "scss")
_register("less", "less css", "lesscss")
_register("tailwindcss", "tailwind", "tailwind css")
_register("bootstrap", "bootstrap5", "bootstrap4")
_register("antd", "ant design", "ant-design")
_register("element-ui", "element ui", "elementui", "element-plus", "element plus")

# --- Python ecosystem ---
_register("python", "python3", "python2", "py")
_register("django", "django rest framework", "drf")
_register("flask", "flask-restful")
_register("fastapi", "fast api")
_register("pytorch", "torch")
_register("tensorflow", "tf")
_register("pandas", "pd")
_register("numpy", "np")
_register("scikit-learn", "sklearn", "scikit learn")
_register("celery", "celery task queue")

# --- Java ecosystem ---
_register("java", "jdk", "jre")
_register("spring", "spring framework")
_register("spring boot", "springboot", "spring-boot")
_register("spring cloud", "springcloud", "spring-cloud")
_register("mybatis", "mybatis-plus", "mybatisplus")

# --- Go ---
_register("go", "golang", "go lang")
_register("gin", "gin framework", "gin-gonic")

# --- Rust ---
_register("rust", "rust lang", "rustlang")

# --- C / C++ ---
_register("c++", "cpp", "cplusplus", "c plus plus")
_register("c#", "csharp", "c sharp")
_register("c", "c language", "c lang")
_register(".net", "dotnet", "dot net", ".net core", "dotnet core")

# --- Databases ---
_register("mysql", "mariadb")
_register("postgresql", "postgres", "pg", "pgsql")
_register("mongodb", "mongo")
_register("redis", "redis cache")
_register("elasticsearch", "es", "elastic search", "elastic")
_register("sqlite", "sqlite3")
_register("oracle", "oracle db", "oracledb")
_register("sql server", "mssql", "ms sql", "microsoft sql server")
_register("cassandra", "apache cassandra")
_register("neo4j", "neo4j graph")

# --- DevOps / Cloud ---
_register("docker", "docker container")
_register("kubernetes", "k8s", "kube")
_register("aws", "amazon web services")
_register("gcp", "google cloud", "google cloud platform")
_register("azure", "microsoft azure")
_register("terraform", "tf iac")
_register("ansible", "ansible playbook")
_register("jenkins", "jenkins ci")
_register("github actions", "gh actions")
_register("gitlab ci", "gitlab-ci", "gitlab ci/cd")
_register("nginx", "nginx proxy")
_register("linux", "gnu/linux")
_register("ubuntu", "ubuntu linux")
_register("centos", "centos linux")

# --- Message Queues ---
_register("kafka", "apache kafka")
_register("rabbitmq", "rabbit mq", "rabbit")
_register("rocketmq", "rocket mq")

# --- Mobile ---
_register("react native", "rn", "react-native")
_register("flutter", "flutter sdk")
_register("swift", "swift ui", "swiftui")
_register("kotlin", "kotlin android")
_register("objective-c", "objc", "obj-c")

# --- AI / ML ---
_register("machine learning", "ml")
_register("deep learning", "dl")
_register("natural language processing", "nlp")
_register("computer vision", "cv")
_register("large language model", "llm", "大语言模型", "大模型")
_register("reinforcement learning", "rl", "强化学习")

# --- General ---
_register("restful api", "rest api", "rest", "restful")
_register("graphql", "graph ql")
_register("grpc", "g-rpc")
_register("websocket", "ws", "web socket")
_register("git", "git version control")
_register("svn", "subversion")
_register("agile", "scrum", "敏捷开发")
_register("ci/cd", "cicd", "ci cd", "持续集成")
_register("microservices", "micro services", "微服务", "微服务架构")
_register("分布式系统", "distributed systems", "distributed system")


def normalize_skill_name(name: str) -> str:
    """Return the canonical form of a skill name.

    >>> normalize_skill_name("React.js")
    'react'
    >>> normalize_skill_name("PostgreSQL")
    'postgresql'
    >>> normalize_skill_name("Unknown Skill")
    'unknown skill'
    """
    key = name.strip().lower()
    return _ALIAS_TABLE.get(key, key)
