local os = require("os")
local botId = require("id")

local clientVersion = "0.0.1"

local sides = require("sides")
local robot = require("robot")
local shell = require("shell")
local computer = require("computer")

local component = require("component")
if not component.isAvailable("internet") then
  print("Internet card not found.")
  return
end
local internet = require("internet")
if not component.isAvailable("inventory_controller") then
  print("Inventory controller not found.")
  return
end
local inv_controller = component.inventory_controller


-- Can be nil if component isn't installed
local crafting = component.isAvailable("crafting") and component.crafting or nil

local connection


local function split(input)
  local results = {}
  for token in input:gmatch("([^%s]+)") do
    table.insert(results, token)
  end
  return results
end


-- Represent table as JSON string
-- TODO: Add support for arrays
local function toJson(table)
  local json = "{"
  for key, value in pairs(table) do
    json = json .. "\"" .. key .. "\": "
    if type(value) == "table" then
      json = json .. toJson(value):sub(1, -2) .. ","
    elseif type(value) == "string" then
      json = json .. "\"" .. value .. "\","
    else
      json = json .. tostring(value) .. ","
    end
  end
  -- Remove trailing comma
  json = json:sub(1, -2) .. "};"
  return json
end


local function connect()
  print("Connecting to server")
  local reason
  while true do
    connection, reason = internet.open("localhost:3")
    if connection then
      connection:write(tostring(botId) .. ";")
      connection:flush()
      
      connection:setTimeout(3)
      local success, data = pcall(connection.read, connection)
      if success and data == "ack;" then
        connection:setTimeout(0.01)
        print("Server connection established")
        break
      end
    end
    
    print("Failed to connect to server.\n".. reason or "nil" .."\nRetrying in 3 seconds.")
    connection:close()
    os.sleep(3)
  end
end


-- Receive a single command from the server.
-- Blocks until a message is received, and reconnects 
-- automatically if the connection terminates unexpectedly.
local function receive()
  local message = ""
  while not (message:sub(-1) == ";") do
    local success, data = pcall(connection.read, connection)
    -- Not success -> timeout. success + no data -> connection lost
    if success then
      if not data then
        print("Lost connection to server")
        connection:close()
        connect()
      else
        message = message..data
      end
    end
  end
  return message:sub(1, -2)
end


local function move(command)
  -- Main loop will flush written response after returning
  local success, reason = false, "Invalid or missing direction"

  if command[2] == "front" then
    success, reason = robot.forward()
  elseif command[2] == "up" then
    success, reason = robot.up()
  elseif command[2] == "down" then
    success, reason = robot.down()
  elseif command[2] == "back" then
    success, reason = robot.back()
  elseif command[2] == "left" then
    robot.turnLeft()
    success, reason = robot.forward()
    robot.turnRight()
  elseif command[2] == "right" then
    robot.turnRight()
    success, reason = robot.forward()
    robot.turnLeft()
  end

  if success then
    connection:write("{\"success\": true};")
  else
    connection:write("{\"success\": false, \"error\": \"" .. reason .. "\"};")
  end
end


local function loop()
  local exit = false
  while not exit do
    local success, err = pcall(function()
      local command = receive()
      print("Received command: " .. command)
      command = split(command)

      if command[1] == "ping" then
        connection:write("{\"success\": true};")

      elseif command[1] == "version" then
        connection:write("{\"success\": true, \"version\": \"" .. clientVersion .. "\"};")

      elseif command[1] == "memory" then
        connection:write(toJson({success = true, free = computer.freeMemory(), total = computer.totalMemory() }))

      elseif command[1] == "move" then
        move(command)

      elseif command[1] == "turn" then
        if command[2] == "left" then
          robot.turnLeft()
          connection:write("{\"success\": true};")
        elseif command[2] == "right" then
          robot.turnRight()
          connection:write("{\"success\": true};")
        else
          connection:write("{\"success\": false, \"error\": \"Missing or unknown direction\"};")
        end

      elseif command[1] == "detect" then
        local passable, type = robot.detect()
        local passableUp, typeUp = robot.detectUp()
        local passableDown, typeDown = robot.detectDown()
        connection:write(toJson({success = true, front = {passable = passable, type = type}, up = {passable = passableUp, type = typeUp}, down = {passable = passableDown, type = typeDown}}))

      elseif command[1] == "use" then
        local sneaky = command[2] == "true"
        local success, reason = robot.use(sides.front, sneaky)
        if success then
          connection:write("{\"success\": true};")
        else
          connection:write("{\"success\": false, \"error\": \"" .. reason .. "\"};")
        end
        
      elseif command[1] == "insert" then

        local robot_slot = command[2]
        local dest_slot = command[3]
        local count = tonumber(command[4] or 1)

        if not robot_slot or not dest_slot then
          connection:write("{\"success\": false, \"error\": \"Missing slot argument\"};")
        else 
          robot_slot = tonumber(robot_slot)
          dest_slot = tonumber(dest_slot)
          robot.select(robot_slot)
          local success, reason = inv_controller.dropIntoSlot(sides.front, dest_slot, count)
          if success then
            connection:write("{\"success\": true};")
          else
            connection:write("{\"success\": false, \"error\": \"" .. reason .. "\"};")
          end
        end

      elseif command[1] == "inventory" then
        local inventory = {}
        for i = 1, robot.inventorySize() do
          local stack = inv_controller.getStackInInternalSlot(i)
          if stack then
            -- Many modded items share an ID, and are distinguished by their data value
            inventory[i] = {name = stack.name, count = stack.size, dataValue = stack.damage}
          end
        end
        connection:write(toJson({success = true, inventory = inventory, size = robot.inventorySize()}))

      elseif command[1] == "craft" then
        -- Crafting recipe must be placed in a 3x3 area 
        -- in the top-left of the robot's inventory
        if not crafting then
          connection:write("{\"success\": false, \"error\": \"Crafting module not installed\"};")
          return
        end

        local count = tonumber(command[2])
        local success = crafting.craft(count);
        if success then
          connection:write("{\"success\": true};")
        else
          connection:write("{\"success\": false, \"error\": \"Failed to craft item\"};")
        end

      elseif command[1] == "reboot" then
        computer.shutdown(true)

      elseif command[1] == "update" then
        -- Download new copy of client.lua
        -- Allows updating existing robots during development
        local ok, err = shell.execute("wget -f http://localhost/client client.lua")
        if not ok then
          connection:write("{\"success\": false, \"error\": \"" .. err or "nil" .. "\"};")
        else
          connection:write("{\"success\": true};")
        end
        connection:flush()
        connection:close()
        
        local ok, err = shell.execute("client.lua")
        if not ok then
          print("Error restarting client: " .. err)
        end
        exit = true

      elseif command[1] == "exit" then
        connection:write("{\"success\": true};")
        connection:flush()
        connection:close()
        exit = true
      else
        connection:write(toJson({success = false, error = " Unknown command: " .. command[1] }))
      end
      connection:flush()
    end)

    if not success then
      print("Error: " .. err)
      connection:write(toJson({success = false, error = err}))
      connection:flush()
    end    
  end
end


print("\nStarting robot client version " .. clientVersion .. "\n")

connect()
loop()