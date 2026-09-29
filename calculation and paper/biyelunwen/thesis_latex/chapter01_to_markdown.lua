-- The editable source is LaTeX; this filter exports the numbered reading copy.
local keys = {
  "woloszyn2022", "chen2022", "akomah2002", "schaefer2011",
  "delgado2005", "thiel2020", "ditchfield1995", "schaefer2019",
  "jiang2024", "torrence1998", "cawley2010"
}
local numbers = {}
for index, key in ipairs(keys) do numbers[key] = index end
local section, subsection = 0, 0

function Cite(element)
  local labels = {}
  for _, citation in ipairs(element.citations) do
    assert(numbers[citation.id], "Unknown reference: " .. citation.id)
    labels[#labels + 1] = tostring(numbers[citation.id])
  end
  return pandoc.Str("[" .. table.concat(labels, ",") .. "]")
end

function Header(element)
  local title = pandoc.utils.stringify(element.content)
  if element.level == 1 then
    element.content = {pandoc.Str("第一章 " .. title)}
  elseif element.level == 2 then
    section, subsection = section + 1, 0
    element.content = {pandoc.Str("1." .. section .. " " .. title)}
  elseif element.level == 3 then
    subsection = subsection + 1
    element.content = {pandoc.Str("1." .. section .. "." .. subsection .. " " .. title)}
  end
  return element
end

function Div(element)
  if element.classes[1] ~= "thebibliography" then return element end
  local blocks = {pandoc.Header(2, "参考文献")}
  local count = 0
  for _, block in ipairs(element.content) do
    if block.t == "Para" and pandoc.utils.stringify(block) ~= "99" then
      count = count + 1
      block.content:insert(1, pandoc.Space())
      block.content:insert(1, pandoc.Str("[" .. count .. "]"))
      blocks[#blocks + 1] = block
    end
  end
  assert(count == #keys, "Bibliography count changed; update the export filter.")
  return blocks
end
