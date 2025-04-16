local os = require("os")
local component = require("component")

local clientVersion = "0.0.6"

-- The client script is also copied into the computer that activates the assembler
if not component.isAvailable("robot") then
  print("Not running on robot. Attempting to activate assembler")

  if not component.isAvailable("assembler") then
    print("Failed: Assembler not connected")
    return
  end
  component.assembler.start()
  os.exit()
end

local botId = require("id")
local sides = require("sides")
local robot = require("robot")
local shell = require("shell")
local computer = require("computer")

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

if not component.isAvailable("geolyzer") then
  print("Geolyzer not found.")
  return
end
local geolyzer = component.geolyzer

if not component.isAvailable("crafting") then
  print("Crafting upgrade not found.")
  return
end
local crafting = component.crafting

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
  while true do
    connection = internet.open("localhost:3000")
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
    
    print("Failed to connect to server.\nRetrying in 3 seconds.")
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


local function acknowledge_or_error(success, error)
  if success then
    connection:write("{\"success\": true};")
  else
    connection:write("{\"success\": false, \"error\": \"" .. error .. "\"};")
  end
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

  acknowledge_or_error(success, reason)
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
        local success, action_type = robot.use(sides.front, sneaky)
        if success then
          connection:write("{\"success\": true, \"action\": \"" .. action_type .. "\"};")
        else
          connection:write("{\"success\": false, \"error\": \"No action taken\"};")
        end
        
      elseif command[1] == "place" then
        local side = command[2]

        local success
        local obstructed
        local errorMessage = "Failed to place"
        if robot.count() == 0 then
          success = false
          errorMessage = "Selected inventory slot is empty"
        elseif side == "front" or side == nil then
          success = robot.place()
          obstructed = robot.detect()
        elseif side == "up" then
          success = robot.placeUp()
          obstructed = robot.detectUp()
        elseif side == "down" then
          success = robot.placeDown()
          obstructed = robot.detectDown()
        else
          success = false
          errorMessage = "Invalid side"
        end

        if obstructed and not success then
          errorMessage = "Placement obstructed"
        end

        acknowledge_or_error(success, errorMessage)

      elseif command[1] == "swing" then
        local side = command[2]

        local success
        local errorMessage = "Failed to mine"
        if side == "front" or side == nil then
          success = robot.swing()
        elseif side == "up" then
          success = robot.swingUp()
        elseif side == "down" then
          success = robot.swingDown()
        else
          success = false
          errorMessage = "Invalid side"
        end

        acknowledge_or_error(success, errorMessage)

      elseif command[1] == "insert" then
        local side = command[2]
        local dest_slot = tonumber(command[3])
        local count = tonumber(command[4] or 1)

        if side ~= "front" and side ~= "up" and side ~= "down" then
          connection:write("{\"success\": false, \"error\": \"Invalid side\"};")
        elseif not dest_slot then
          connection:write("{\"success\": false, \"error\": \"Missing or invalid destination slot\"};")
        else
          local success, reason = inv_controller.dropIntoSlot(sides[side], dest_slot, count)
          acknowledge_or_error(success, reason or "Inventory not found or failed to transfer item(s)")
        end

      elseif command[1] == "select" then
        local slot = tonumber(command[2])
        if not slot then
          connection:write("{\"success\": false, \"error\": \"Missing slot argument\"};")
        elseif slot > robot.inventorySize() then
          connection:write("{\"success\": false, \"error\": \"Slot out of bounds\"};")
        end
        robot.select(slot)
        connection:write("{\"success\": true};")

      elseif command[1] == "transfer" then
        local source_slot = tonumber(command[2])
        local dest_slot = tonumber(command[3])
        local count = tonumber(command[4])

        if not source_slot or not dest_slot then
          connection:write("{\"success\": false, \"error\": \"Invalid or missing slot argument\"};")
        elseif source_slot > robot.inventorySize() or dest_slot > robot.inventorySize() then
          connection:write("{\"success\": false, \"error\": \"Source or destination out of bounds\"};")
        else
          robot.select(source_slot)
          robot.transferTo(dest_slot, count)
          connection:write("{\"success\": true};")
        end

      elseif command[1] == "take" then
        local side = command[2]
        local slot = tonumber(command[3])
        if side == "front" or side == "down" or side == "up" then
          if slot ~= nil then
            local success = inv_controller.suckFromSlot(sides[side], slot)
            acknowledge_or_error(success, "Failed to transfer item(s)")
          else
            connection:write("{\"success\": false, \"error\": \"Invalid or missing slot number argument\"};")
          end
        else
          connection:write("{\"success\": false, \"error\": \"Invalid side\"};")
        end

      elseif command[1] == "read" then
        -- Read the contents of a slot from an adjacent inventory
        local side = command[2]
        local slot = tonumber(command[3])
        if side == "front" or side == "down" or side == "up" then
          if slot ~= nil then
            local stack = inv_controller.getStackInSlot(sides[side], slot)
            if stack then
              -- Many modded items share an ID, and are distinguished by their data value
              connection:write(toJson({success = true, stack = {name = stack.name, count = stack.size, dataValue = stack.damage}}))
            else
              connection:write("{\"success\": true, \"stack\": null};")
            end
          else
            connection:write("{\"success\": false, \"error\": \"Invalid or missing slot number argument\"};")
          end
        else
          connection:write("{\"success\": false, \"error\": \"Invalid side\"};")
        end

      elseif command[1] == "equip" then
        local slot = command[2]
        local error = false

        -- Use either the currently selected slot or the one specified in the argument
        if slot then
          slot = tonumber(slot)
          if (not slot) or slot > robot.inventorySize() then
            connection:write("{\"success\": false, \"error\": \"Invalid slot argument\"};")
            error = true
          else 
            robot.select(slot)
          end
        end
        
        if not error then
          local success = inv_controller.equip()
          acknowledge_or_error(success, "Unable to equip item")
        end

      elseif command[1] == "drop" then
        local quantity = tonumber(command[2])
        local success = robot.dropUp(quantity)
        acknowledge_or_error(success, "Items not removed from inventory")

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

      elseif command[1] == "durability" then
        -- Get the durability of the currently equipped item as a value from 0 - 1, where 1 is full durability.
        local durability, reason = robot.durability()
        
        if durability == nil then
          connection:write(toJson({success = false, error = reason}))
        else
          connection:write(toJson({success = true, durability = durability}))
        end

      elseif command[1] == "craft" then
        -- Crafting recipe must be placed in a 3x3 area 
        -- in the top-left of the robot's inventory
        if not crafting then
          connection:write("{\"success\": false, \"error\": \"Crafting module not installed\"};")
          return
        end

        local count = tonumber(command[2])
        local success = crafting.craft(count);
        acknowledge_or_error(success, "Recipe invalid")

      elseif command[1] == "scan" then
        local radius = tonumber(command[2]) or 12

        if radius > 15 then
          connection:write("{\"success\": false, \"error\": \"radius too large (max 15)\"};")
        elseif radius < 1 then
          connection:write("{\"success\": false, \"error\": \"radius invalid\"};")
        else

          connection:write("{\"success\": true, \"data\": {")

          local width = radius*2 + 1
          for x = 0, width-1 do
            local y_section = {}
            for y = 0, width-1 do
              -- Arguments in x, z, y order
              -- Call returns a 64 element array, we need elements 1:width
              local z_section = geolyzer.scan(x - radius, -radius, y - radius, 1, width, 1)
              local z_data = {}
              for z = 1, width do
                z_data[z-1] = z_section[z]
              end
              y_section[y] = z_data
            end
            if x > 0 then connection:write(", ") end
            connection:write("\"" .. tostring(x) .. "\": " .. toJson(y_section):sub(1, -2))
            connection:flush()
          end
          connection:write("}};")
        end

      elseif command[1] == "reboot" then
        computer.shutdown(true)

      elseif command[1] == "update" then
        -- Download new copy of client.lua
        -- Allows updating existing robots during development
        local ok, err = shell.execute("wget -f http://localhost:8080/client client.lua")
        if not ok then
          connection:write("{\"success\": false, \"error\": \"" .. err or "nil" .. "\"};")
        else
          connection:write("{\"success\": true};")
          connection:flush()
          connection:close()
          
          local ok, err = shell.execute("client.lua")
          if not ok then
            print("Error restarting client: " .. err)
          end
          exit = true
        end

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
