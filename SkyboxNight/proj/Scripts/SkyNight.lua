-- SkyNight.lua
-- Night sky, two layers:
--   SM_SkyDomeNight (this node, opaque): gradient + static stars + horizon haze
--   SM_CloudDomeNight (child, translucent): clouds, scrolled by the wind
-- Stars are static by default (no motion = no shimmer); set starSpeed to give
-- them a slow independent drift. Attach to the SkyDomeNight StaticMesh3D node.

SkyNight = {}

function SkyNight:Create()
    self.windSpeed = 0.012
    self.windDirX = 1.0
    self.windDirY = 0.35
    self.starSpeed = 0.0
    self.twinkle = 1.0
    self.twinkleSpeed = 1.0
    self.time = 0.0
end

function SkyNight:GatherProperties()
    return
    {
        { name = "windSpeed", type = DatumType.Float },
        { name = "windDirX", type = DatumType.Float },
        { name = "windDirY", type = DatumType.Float },
        { name = "starSpeed", type = DatumType.Float },
        { name = "twinkle", type = DatumType.Float },
        { name = "twinkleSpeed", type = DatumType.Float },
    }
end

function SkyNight:UpdateSky(deltaTime)
    if (self.cloudMat == nil) then
        self.cloudMat = LoadAsset("M_CloudsNight")
        self.skyMat = LoadAsset("M_SkyNight")
        if (self.cloudMat == nil) then
            Log.Error("SkyNight: M_CloudsNight material not found")
            return
        end
        self:EnableCollision(false)
        self:EnableOverlaps(false)
    end

    self.time = self.time + deltaTime

    -- clouds scroll with the wind on their own dome
    local len = math.sqrt(self.windDirX * self.windDirX + self.windDirY * self.windDirY)
    if (len < 0.0001) then len = 1.0 end
    local ox = (self.windDirX / len) * self.windSpeed * self.time
    local oy = (self.windDirY / len) * self.windSpeed * self.time
    self.cloudMat:SetUvOffset(Vec(ox - math.floor(ox), oy - math.floor(oy)), 1)

    -- star twinkle: slow sub-texel drift of the star layer's UV0. Bilinear
    -- filtering swings each star dim -> bright -> dim as the sample point
    -- crosses its texel; every star sits at a different sub-texel phase, so
    -- they pulse independently. Uniform (fisheye) mapping keeps it even.
    -- Plus optional slow drift (opposite the wind); starSpeed 0 = anchored.
    if (self.skyMat ~= nil) then
        local texel = 1.0 / 1024.0
        local ts = self.time * self.twinkleSpeed
        local jx = self.twinkle * texel * (0.32 * math.sin(ts * 0.9)
                                         + 0.20 * math.sin(ts * 1.53 + 1.1))
        local jy = self.twinkle * texel * (0.32 * math.sin(ts * 1.17 + 0.6)
                                         + 0.20 * math.sin(ts * 0.71 + 2.4))
        local sx = -(self.windDirX / len) * self.starSpeed * self.time + jx
        local sy = -(self.windDirY / len) * self.starSpeed * self.time + jy
        self.skyMat:SetUvOffset(Vec(sx - math.floor(sx), sy - math.floor(sy)), 1)
    end

    -- camera-anchored dome (child cloud dome follows automatically)
    local world = self:GetWorld()
    local cam = world and world:GetActiveCamera()
    if (cam ~= nil) then
        self:SetWorldPosition(cam:GetWorldPosition())
    end
end

function SkyNight:Tick(deltaTime)
    self:UpdateSky(deltaTime)
end

function SkyNight:EditorTick(deltaTime)
    self:UpdateSky(deltaTime)
end
