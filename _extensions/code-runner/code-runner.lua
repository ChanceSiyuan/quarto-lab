--[[
code-runner.lua - A Lua filter to create interactive code runner widgets

Usage in .qmd files:
  ```{runpy}
  print("Hello Python")
  ```

  ```{runjulia}
  println("Hello Julia")
  ```

  ```{runmma}
  Print["Hello Mathematica"]
  ```

Optional attributes:
  ```{runpy height="400px" title="My Runner"}
  code here
  ```
]]

PANDOC_VERSION:must_be_at_least '3.0'

local pandoc = require 'pandoc'

-- Runtime mapping: class name -> {runtime_id, display_name}
-- Use with dot prefix: ```{.runpy} to avoid Quarto trying to execute with Jupyter
local RUNTIMES = {
  runpy = { id = "python", name = "Python (Server)" },
  runjulia = { id = "julia", name = "Julia (Server)" },
  runmma = { id = "mathematica", name = "Mathematica (Server)" },
  -- Also support without 'run' prefix
  ["server-python"] = { id = "python", name = "Python (Server)" },
  ["server-julia"] = { id = "julia", name = "Julia (Server)" },
  ["server-mma"] = { id = "mathematica", name = "Mathematica (Server)" },
}

-- Track if we've already injected CSS/JS
local resources_injected = false

-- Counter for unique IDs
local runner_count = 0

-- Get the extension's resource directory
local function get_resource_path(filename)
  local script_path = debug.getinfo(1, "S").source:sub(2)
  local script_dir = script_path:match("(.*/)")
  return script_dir .. filename
end

-- Read a file's contents
local function read_file(filepath)
  local fh = io.open(filepath, 'rb')
  if not fh then return nil end
  local contents = fh:read('a')
  fh:close()
  return contents
end

-- Create the CSS/JS injection blocks (only once per document)
local function get_resources()
  if resources_injected then
    return {}
  end
  resources_injected = true

  local css_content = read_file(get_resource_path("code-runner.css"))
  local js_content = read_file(get_resource_path("code-runner.js"))

  local blocks = {}
  
  if css_content then
    table.insert(blocks, pandoc.RawBlock('html', '<style>\n' .. css_content .. '\n</style>'))
  end
  
  if js_content then
    table.insert(blocks, pandoc.RawBlock('html', '<script>\n' .. js_content .. '\n</script>'))
  end

  return blocks
end

-- Generate the HTML for a code runner widget
local function create_runner_html(code, runtime_info, attrs)
  runner_count = runner_count + 1
  local id = "code-runner-" .. runner_count
  
  -- Get optional attributes
  local height = attrs.height or "200px"
  local title = attrs.title or (runtime_info.name .. " - qiskit, numpy, scipy available")
  
  -- Escape code for HTML
  local escaped_code = code:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
  
  local html = string.format([[
<div class="code-runner" id="%s" data-runtime="%s">
    <div class="code-runner-header">
        <span class="runtime-label">%s</span>
        <button class="run-btn">▶ Run Code</button>
    </div>
    <textarea class="code-input" spellcheck="false" style="min-height: %s;">%s</textarea>
    <div class="code-runner-output"></div>
</div>
]], id, runtime_info.id, title, height, escaped_code)
  
  return html
end

-- Main filter function for CodeBlock
local function process_codeblock(block)
  if block.t ~= 'CodeBlock' then
    return nil
  end
  
  -- Check if this is a code runner block
  local runtime_info = nil
  local matched_class = nil
  
  for class_name, info in pairs(RUNTIMES) do
    if block.classes:includes(class_name) then
      runtime_info = info
      matched_class = class_name
      break
    end
  end
  
  if not runtime_info then
    return nil  -- Not a code runner block, leave unchanged
  end
  
  -- Build the output blocks
  local result = {}
  
  -- Add CSS/JS resources (only first time)
  local resources = get_resources()
  for _, res in ipairs(resources) do
    table.insert(result, res)
  end
  
  -- Create the runner HTML
  local html = create_runner_html(block.text, runtime_info, block.attributes)
  table.insert(result, pandoc.RawBlock('html', html))
  
  return result
end

return {
  {
    CodeBlock = process_codeblock
  }
}
