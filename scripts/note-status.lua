local status_help = {
  stable = "organized enough to read as a reference",
  draft = "useful but still being edited or incomplete",
  rough = "informal record; may be incomplete or wrong"
}

local function current_input()
  if quarto and quarto.doc and quarto.doc.input_file then
    return quarto.doc.input_file
  end
  if PANDOC_STATE and PANDOC_STATE.input_files and #PANDOC_STATE.input_files > 0 then
    return PANDOC_STATE.input_files[1]
  end
  return ""
end

local function normalize_path(path)
  return (path or ""):gsub("\\", "/")
end

local function section_relative_path(path)
  local theory_start = path:find("theory/", 1, true)
  if theory_start then
    return path:sub(theory_start)
  end
  local experiments_start = path:find("Experiments/", 1, true)
  if experiments_start then
    return path:sub(experiments_start)
  end
  return path
end

local function strip_yaml_quotes(value)
  value = (value or ""):gsub("^%s+", ""):gsub("%s+$", "")
  local first = value:sub(1, 1)
  local last = value:sub(-1)
  if (first == '"' and last == '"') or (first == "'" and last == "'") then
    return value:sub(2, -2)
  end
  return value
end

local function read_text(path)
  local handle = io.open(path, "r")
  if not handle then
    return nil
  end
  local text = handle:read("*a")
  handle:close()
  return text
end

local function frontmatter_value(input_path, key)
  local relpath = section_relative_path(input_path)
  local text = read_text(input_path) or read_text(relpath)
  if not text or not text:match("^%-%-%-") then
    return nil
  end

  local raw = text:match("^%-%-%-%s*\n(.-)\n%-%-%-")
  if not raw then
    return nil
  end

  for line in raw:gmatch("[^\r\n]+") do
    local found_key, value = line:match("^([%w_-]+):%s*(.-)%s*$")
    if found_key == key and value and value ~= "" and value ~= "|" and value ~= ">" then
      return strip_yaml_quotes(value)
    end
  end
  return nil
end

local function is_note_page(path)
  if path == "" then
    return false
  end
  local in_scope = path:find("theory/", 1, true) or path:find("Experiments/", 1, true)
  if not in_scope then
    return false
  end
  return not path:match("/index%.qmd$") and not path:match("^index%.qmd$")
end

local function meta_string(meta, key)
  local value = meta[key]
  if value == nil then
    return nil
  end
  local text = pandoc.utils.stringify(value)
  if text == "" then
    return nil
  end
  return text
end

local function normalize_status(value)
  local status = string.lower(value or "draft")
  if status_help[status] then
    return status
  end
  return "draft"
end

local function env_truthy(name)
  local value = os.getenv(name)
  if not value or value == "" then
    return false
  end
  value = string.lower(value)
  return not (value == "0" or value == "false" or value == "no" or value == "off")
end

local function env_list_contains(name, target)
  local value = os.getenv(name) or ""
  target = string.lower(target)
  for item in value:gmatch("[^,%s]+") do
    if string.lower(item) == target then
      return true
    end
  end
  return false
end

local function should_query_git()
  if env_truthy("QUARTO_SKIP_GIT_STATUS") or env_truthy("QUARTO_SKIP_NAV") then
    return false
  end
  if env_list_contains("QUARTO_PROFILE", "fast") then
    return false
  end
  return not (
    env_truthy("QUARTO_PREVIEW")
    or env_truthy("QUARTO_PROJECT_PREVIEW")
    or env_truthy("QUARTO_RENDER_PREVIEW")
  )
end

local function shell_quote(value)
  return "'" .. value:gsub("'", "'\\''") .. "'"
end

local function git_last_updated(path)
  if not should_query_git() then
    return nil
  end
  if type(io.popen) ~= "function" then
    return nil
  end
  local relpath = section_relative_path(path)
  local command = "git log -1 --format=%cs -- " .. shell_quote(relpath)
  local ok, handle = pcall(io.popen, command)
  if not ok or not handle then
    return nil
  end
  local output = handle:read("*a") or ""
  handle:close()
  output = output:gsub("%s+$", "")
  if output == "" then
    return nil
  end
  return output
end

local function badge_div(status, updated)
  local label_attr = pandoc.Attr("", { "note-status-value", "note-status-" .. status }, {
    title = status_help[status]
  })
  local inlines = {
    pandoc.Str("Status:"),
    pandoc.Space(),
    pandoc.Span({ pandoc.Str(status) }, label_attr),
    pandoc.Space(),
    pandoc.Str("·"),
    pandoc.Space(),
    pandoc.Str("Updated:"),
    pandoc.Space(),
    pandoc.Str(updated)
  }
  return pandoc.Div(
    { pandoc.Plain(inlines) },
    pandoc.Attr("", { "note-status-badge", "note-status-" .. status })
  )
end

function Pandoc(doc)
  local path = normalize_path(current_input())
  if not is_note_page(path) then
    return nil
  end

  local status = normalize_status(frontmatter_value(path, "status") or meta_string(doc.meta, "status"))
  local updated = frontmatter_value(path, "updated")
    or frontmatter_value(path, "date")
    or git_last_updated(path)
    or "not recorded"

  table.insert(doc.blocks, 1, badge_div(status, updated))
  return doc
end
