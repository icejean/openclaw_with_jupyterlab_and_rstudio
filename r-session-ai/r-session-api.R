# ============================================================================
# r-session-api.R — R Session API Server
# ============================================================================
# 在 RStudio Console 中运行本脚本，启动一个轻量级 HTTP API。
# 当前 R session 正常交互不阻塞，AI 助手可通过 API 读取/操作数据。
#
# 使用方法：
#   source("r-session-api.R")
#
# 停止：
#   httpuv::stopServer(server)
#
# 要求：
#   install.packages(c("httpuv", "jsonlite"))
# ============================================================================

# --- 配置 ------------------------------------------------------------------
# 端口优先级：环境变量 R_API_PORT > R options() > 默认 8161
env_port <- Sys.getenv("R_API_PORT", unset = NA)
if (!is.na(env_port)) {
  options(rsession_api_port = as.integer(env_port))
} else if (is.null(getOption("rsession_api_port"))) {
  options(rsession_api_port = 8161)
}
options(rsession_api_host = "127.0.0.1")    # 仅本地访问
options(rsession_api_max_rows = 100)        # 预览数据最大行数
options(rsession_api_max_str = 20)          # str 截断层级
# API Token 认证
# 优先级：R选项 rsession_api_token > 环境变量 R_API_TOKEN > 空（不启用）
API_TOKEN <- getOption("rsession_api_token", Sys.getenv("R_API_TOKEN", unset = ""))
if (nchar(API_TOKEN) > 0) {
  cat(sprintf("🔐 API Token 认证已启用\n"))
} else {
  cat("⚠️  API Token 未配置（仅 127.0.0.1 绑定，内网安全可接受）\n")
}

# --- 依赖 ------------------------------------------------------------------
library(httpuv)
library(jsonlite)

PORT   <- getOption("rsession_api_port")
HOST   <- getOption("rsession_api_host")
MAX_ROW <- getOption("rsession_api_max_rows")

# --- 辅助函数 --------------------------------------------------------------

# 安全转 R 对象 → JSON 可序列化结构
obj_to_list <- function(name, obj, depth = 0, max_depth = 2) {
  info <- list(
    name   = name,
    class  = class(obj),
    type   = typeof(obj),
    size   = as.numeric(object.size(obj))
  )

  if (depth >= max_depth) {
    return(info)
  }

  if (is.data.frame(obj) || is.matrix(obj)) {
    info$dim <- dim(obj)
    info$dimnames <- dimnames(obj)
    if (is.data.frame(obj)) {
      info$colnames <- names(obj)
      info$dtypes <- sapply(obj, function(col) class(col)[1])
      info$nrow <- nrow(obj)
      info$ncol <- ncol(obj)
    }
  } else if (is.list(obj) && !is.data.frame(obj)) {
    info$length <- length(obj)
    info$names  <- names(obj)
  } else if (is.atomic(obj) && length(obj) <= 100) {
    info$length <- length(obj)
    info$values <- obj
  } else if (is.atomic(obj)) {
    info$length <- length(obj)
    info$summary <- summary(obj)
  } else if (is.function(obj)) {
    info$args <- capture.output(args(obj))
  }

  # 环境信息
  if (is.environment(obj) && !identical(obj, .GlobalEnv)) {
    info$n_objects <- length(ls(envir = obj))
  }

  return(info)
}

# 安全执行 R 代码
safe_eval <- function(code, env = .GlobalEnv, console_echo = TRUE) {
  # 记录执行前环境中的对象列表
  before <- ls(envir = env)

  # 执行代码，同时捕获输出和可能的错误
  output <- character()
  result <- NULL
  error  <- NULL

  tryCatch({
    if (console_echo) {
      # sink 到临时文件，split=TRUE 同时输出到 Console
      tf <- tempfile("recho_")
      sink(tf, split = TRUE)
      on.exit({ sink(); unlink(tf) }, add = TRUE)
      visible <- withVisible(eval(parse(text = code), envir = env))
      sink()
      output <- readLines(tf, warn = FALSE)
      unlink(tf)
    } else {
      # 静默模式：capture.output 不输出到 Console
      output <- capture.output({
        visible <- withVisible(eval(parse(text = code), envir = env))
      })
    }
    result <- if (visible$visible) visible$value else NULL
  }, error = function(e) {
    error <<- e$message
  })

  # 检测新创建/修改的对象
  after <- ls(envir = env)
  new_objs <- setdiff(after, before)

  list(
    success  = is.null(error),
    error    = error,
    output   = output,
    result   = result,
    new_objs = new_objs,
    changed  = length(new_objs) > 0
  )
}

# str 截断
safe_str <- function(obj) {
  capture.output(str(obj,
    max.level = getOption("rsession_api_max_str"),
    give.attr = FALSE
  ))
}

# 简单的模板响应
ok <- function(data) {
  list(
    status = 200L,
    headers = list(
      "Content-Type" = "application/json; charset=utf-8",
      "Access-Control-Allow-Origin" = "*"
    ),
    body = toJSON(list(success = TRUE, data = data), auto_unbox = TRUE, force = TRUE)
  )
}

err <- function(msg, status = 400L) {
  list(
    status = status,
    headers = list(
      "Content-Type" = "application/json; charset=utf-8",
      "Access-Control-Allow-Origin" = "*"
    ),
    body = toJSON(list(success = FALSE, error = msg), auto_unbox = TRUE)
  )
}

parse_json_body <- function(req) {
  raw_body <- tryCatch(req$rook.input$read(), error = function(e) NULL)
  if (is.null(raw_body) || length(raw_body) == 0) {
    return(NULL)
  }
  txt <- rawToChar(raw_body)
  Encoding(txt) <- "UTF-8"
  tryCatch(fromJSON(txt), error = function(e) NULL)
}

# --- 路由分发 --------------------------------------------------------------

app <- list(
  call = function(req) {
    method <- req$REQUEST_METHOD
    path   <- req$PATH_INFO

    # CORS 预检
    if (method == "OPTIONS") {
      return(list(
        status = 200L,
        headers = list(
          "Access-Control-Allow-Origin"  = "*",
          "Access-Control-Allow-Methods" = "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers" = "Content-Type, Authorization"
        ),
        body = ""
      ))
    }

    # ── API Token 认证 ────────────────────────────────────────────
    if (nchar(API_TOKEN) > 0) {
      auth_header <- req$HTTP_AUTHORIZATION %||% ""
      token <- sub("^Bearer[[:space:]]+", "", auth_header)
      if (token != API_TOKEN) {
        return(list(
          status = 401L,
          headers = list(
            "Content-Type" = "application/json; charset=utf-8",
            "Access-Control-Allow-Origin" = "*"
          ),
          body = toJSON(list(success = FALSE, error = "unauthorized"), auto_unbox = TRUE)
        ))
      }
    }

    tryCatch({

      # ======================================================================
      # GET /health — 健康检查
      # ======================================================================
      if (path == "/health" && method == "GET") {
        return(ok(list(
          status = "alive",
          r_version = R.version.string,
          pid = Sys.getpid(),
          host = HOST,
          port = PORT
        )))
      }

      # ======================================================================
      # GET /env — 列出环境变量
      # ======================================================================
      if (path == "/env" && method == "GET") {
        objs <- ls(envir = .GlobalEnv)
        data <- lapply(objs, function(n) obj_to_list(n, get(n, envir = .GlobalEnv)))
        names(data) <- objs
        return(ok(list(
          objects = data,
          count   = length(objs)
        )))
      }

      # ======================================================================
      # GET /packages — 列出已加载的包
      # ======================================================================
      if (path == "/packages" && method == "GET") {
        pkgs <- loadedNamespaces()
        versions <- sapply(pkgs, function(p) {
          tryCatch(as.character(packageVersion(p)), error = function(e) "unknown")
        })
        return(ok(list(
          packages = as.list(versions),
          count    = length(pkgs)
        )))
      }

      # ======================================================================
      # GET /preview/{name} — 预览对象
      # ======================================================================
      if (grepl("^/preview/", path) && method == "GET") {
        raw_name <- sub("^/preview/", "", path)
        name <- URLdecode(raw_name)

        if (!exists(name, envir = .GlobalEnv)) {
          return(err(sprintf("对象 '%s' 不存在", name)))
        }

        obj <- get(name, envir = .GlobalEnv)

        result <- list(
          name  = name,
          class = class(obj),
          type  = typeof(obj),
          size  = as.numeric(object.size(obj)),
          str   = safe_str(obj)
        )

        # 数据框 / 矩阵 特殊处理
        if (is.data.frame(obj) || is.matrix(obj)) {
          n_show <- min(MAX_ROW, nrow(obj))
          result$head     <- head(obj, n_show)
          result$summary  <- capture.output(summary(obj))
          result$dim      <- dim(obj)
          result$colnames <- if (is.data.frame(obj)) names(obj) else colnames(obj)
          result$dtypes   <- sapply(as.data.frame(obj), function(col) class(col)[1])
          # 缺失值统计
          if (anyNA(obj)) {
            result$na_count <- sum(is.na(obj))
            na_by_col <- colSums(is.na(as.data.frame(obj)))
            result$na_by_column <- as.list(na_by_col[na_by_col > 0])
          }
        }

        return(ok(result))
      }

      # ======================================================================
      # POST /eval — 执行 R 代码
      # ======================================================================
      if (path == "/eval" && method == "POST") {
        params <- parse_json_body(req)
        if (is.null(params) || is.null(params$code)) {
          return(err("请求体必须包含 'code' 字段"))
        }

        code <- params$code
        ret <- safe_eval(code)

        response <- list(
          success   = ret$success,
          output    = ret$output,
          new_objs  = ret$new_objs,
          changed   = ret$changed
        )

        if (!ret$success) {
          response$error <- ret$error
          # 仍然返回 200，让 AI 自行判断错误信息
          return(ok(response))
        }

        # 如有返回值，尝试序列化
        if (!is.null(ret$result)) {
          if (is.atomic(ret$result) && length(ret$result) <= 1000) {
            response$result <- ret$result
          } else if (is.data.frame(ret$result)) {
            n_show <- min(MAX_ROW, nrow(ret$result))
            response$result <- head(ret$result, n_show)
            response$result_dim <- dim(ret$result)
          } else {
            response$result_str <- capture.output(print(ret$result))
          }
          response$result_class <- class(ret$result)
        }

        return(ok(response))
      }

      # ======================================================================
      # POST /eval/quiet — 执行 R 代码（不打印到 Console）
      # ======================================================================
      if (path == "/eval/quiet" && method == "POST") {
        params <- parse_json_body(req)
        if (is.null(params) || is.null(params$code)) {
          return(err("请求体必须包含 'code' 字段"))
        }

        code <- params$code
        ret <- safe_eval(code, console_echo = FALSE)

        response <- list(success = ret$success, output = ret$output)
        if (!ret$success) {
          response$error <- ret$error
        } else if (!is.null(ret$result)) {
          if (is.atomic(ret$result) && length(ret$result) <= 1000) {
            response$result <- ret$result
          } else if (is.data.frame(ret$result)) {
            n_show <- min(MAX_ROW, nrow(ret$result))
            response$result <- head(ret$result, n_show)
            response$result_dim <- dim(ret$result)
          } else {
            response$result_str <- capture.output(print(ret$result))
          }
          response$result_class <- class(ret$result)
        }

        return(ok(response))
      }

      # 未匹配路由
      return(err(sprintf("未知路径: %s %s", method, path), 404))

    }, error = function(e) {
      list(
        status = 500L,
        headers = list("Content-Type" = "application/json; charset=utf-8"),
        body = toJSON(list(success = FALSE, error = paste("服务器错误:", e$message)), auto_unbox = TRUE)
      )
    })
  }
)

# --- 启动服务器（非阻塞） --------------------------------------------------

server <- startServer(HOST, PORT, app)

# 注册退出时自动停止
reg.finalizer(server, function(s) {
  tryCatch(s$stop(), error = function(e) NULL)
}, onexit = TRUE)

# --- 打印启动信息 ----------------------------------------------------------

cat("\n")
cat("┌─────────────────────────────────────────────┐\n")
cat("│  🦞 R Session API 已启动                     │\n")
cat("├─────────────────────────────────────────────┤\n")
cat(sprintf("│  地址: http://%s:%d               │\n", HOST, PORT))
cat("│                                            │\n")
cat("│  📡 端点列表                                │\n")
cat("│  GET  /health          健康检查              │\n")
cat("│  GET  /env             查看环境变量           │\n")
cat("│  GET  /packages        查看已加载包           │\n")
cat("│  GET  /preview/{name}  预览对象              │\n")
cat("│  POST /eval            执行 R 代码           │\n")
cat("│  POST /eval/quiet      静默执行 R 代码       │\n")
cat("│                                            │\n")
cat("│  📝 注意事项                                │\n")
cat("│  • Console 可继续正常使用 R                   │\n")
cat("│  • API 仅本机可访问 (127.0.0.1)              │\n")
cat(sprintf("│  • Token认证: %-31s│\n", ifelse(nchar(API_TOKEN) > 0, "✅ 已启用", "⚠️  未启用")))
cat("│  • 停止: httpuv::stopServer(server)          │\n")
cat("└─────────────────────────────────────────────┘\n")
cat("\n")
