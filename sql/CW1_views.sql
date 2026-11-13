-- Run CW1_schema.sql first.

SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- Profile overview
CREATE OR ALTER VIEW CW1.vw_MemberProfile
AS
SELECT
    m.MemberId,
    m.Username,
    COALESCE(
        NULLIF(LTRIM(RTRIM(CONCAT(m.FirstName, N' ', m.LastName))), N''),
        m.Username COLLATE DATABASE_DEFAULT
    )                                                                 AS FullName,
    m.Email,
    m.AvatarUrl,
    m.Bio,

    m.LocalityId,
    l.Name                                                            AS LocalityName,
    r.Name                                                            AS RegionName,
    c.Name                                                            AS NationName,
    CASE
        WHEN l.Name IS NULL THEN NULL
        WHEN r.Name IS NULL THEN l.Name
        ELSE l.Name + N', ' + r.Name + N', ' + c.Name
    END                                                               AS DisplayLocation,

    m.PreferredUnitSystem,
    m.PreferredLanguage,
    m.ProfileVisibility,
    m.AccountStatus,
    m.JoinedAt,
    m.LastLoginAt,
    m.EmailVerifiedAt,

    ISNULL(p.PreferenceCount, 0)                                      AS PreferenceCount,
    p.TopActivity,
    p.ActivityList,

    (SELECT COUNT(*) FROM CW1.MemberFollow AS f
      WHERE f.FolloweeMemberId = m.MemberId)                          AS FollowerCount,
    (SELECT COUNT(*) FROM CW1.MemberFollow AS f
      WHERE f.FollowerMemberId = m.MemberId)                          AS FollowingCount
FROM CW1.Member AS m
LEFT JOIN CW1.Locality AS l ON l.LocalityId = m.LocalityId
LEFT JOIN CW1.Region   AS r ON r.RegionId   = l.RegionId
LEFT JOIN CW1.Country  AS c ON c.CountryId  = r.CountryId
OUTER APPLY
(
    SELECT
        COUNT(*)                                                      AS PreferenceCount,
        MAX(CASE WHEN mp.PreferenceRank = 1 THEN aty.Label END)       AS TopActivity,
        STRING_AGG(
            aty.Label + ISNULL(N' (' + sl.Label + N')', N''),
            N', '
        ) WITHIN GROUP (ORDER BY mp.PreferenceRank)                   AS ActivityList
    FROM CW1.MemberPreference AS mp
    JOIN CW1.ActivityType     AS aty ON aty.ActivityTypeId = mp.ActivityTypeId
    LEFT JOIN CW1.SkillLevel  AS sl  ON sl.SkillLevelId    = mp.SkillLevelId
    WHERE mp.MemberId = m.MemberId
) AS p
;
GO

-- Preference details
CREATE OR ALTER VIEW CW1.vw_MemberPreferenceDetail
AS
SELECT
    m.MemberId,
    m.Username,
    mp.PreferenceRank,
    aty.ActivityTypeId,
    aty.Slug                                                          AS ActivitySlug,
    aty.Label                                                         AS ActivityName,
    ac.Name                                                           AS CategoryName,
    sl.SkillLevelId,
    sl.Code                                                           AS SkillCode,
    sl.Label                                                          AS SkillLabel,
    sl.MaxTrailDifficulty,
    mp.CreatedAt
FROM CW1.MemberPreference AS mp
JOIN CW1.Member           AS m   ON m.MemberId        = mp.MemberId
JOIN CW1.ActivityType     AS aty ON aty.ActivityTypeId = mp.ActivityTypeId
JOIN CW1.ActivityCategory AS ac  ON ac.CategoryId      = aty.CategoryId
LEFT JOIN CW1.SkillLevel  AS sl  ON sl.SkillLevelId    = mp.SkillLevelId;
GO

-- Verification queries
SELECT
    MemberId,
    Username,
    FullName,
    DisplayLocation,
    PreferenceCount,
    TopActivity,
    ActivityList,
    FollowingCount AS [Following],
    FollowerCount,
    ProfileVisibility,
    AccountStatus
FROM CW1.vw_MemberProfile
ORDER BY MemberId;
GO

SELECT
    (SELECT COUNT(*) FROM CW1.Member)          AS MemberRows,
    (SELECT COUNT(*) FROM CW1.vw_MemberProfile) AS ViewRows,
    CASE WHEN (SELECT COUNT(*) FROM CW1.Member)
            = (SELECT COUNT(*) FROM CW1.vw_MemberProfile)
         THEN N'PASS: one row per member'
         ELSE N'FAIL: join duplicated rows'
    END                                            AS CardinalityCheck;
GO

SELECT
    NationName,
    COUNT(*) AS Members
FROM CW1.vw_MemberProfile
GROUP BY NationName
ORDER BY NationName;
GO

SELECT
    Username, FullName, DisplayLocation, Bio,
    ActivityList, PreferenceCount, FollowerCount, FollowingCount, JoinedAt
FROM CW1.vw_MemberProfile
WHERE Username = N'megan.pryce';
GO

SELECT
    Username, PreferenceRank, ActivityName, CategoryName,
    ISNULL(SkillLabel, N'(unset)') AS SkillLabel, MaxTrailDifficulty
FROM CW1.vw_MemberPreferenceDetail
WHERE Username = N'callum.fraser'
ORDER BY PreferenceRank;
GO
