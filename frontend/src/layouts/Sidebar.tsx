import { Box, Flex, Text } from "@chakra-ui/react";
import { NavLink } from "react-router-dom";
import { Boxes, LayoutDashboard, Plane, ScanSearch } from "lucide-react";
import { useUiStore } from "@/stores/uiStore";
import { StatusDot } from "@/components/ui/StatusDot";

const SECTIONS = [
  {
    title: null,
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    title: "Pages",
    items: [
      { to: "/voo", label: "Voo", icon: Plane },
      { to: "/datasets", label: "Dataset", icon: Boxes },
    ],
  },
  {
    title: "Aplicação",
    items: [{ to: "/inspecao", label: "Inspeção", icon: ScanSearch }],
  },
] as const;

export function Sidebar() {
  const eventsConnected = useUiStore((state) => state.eventsConnected);

  return (
    <Box
      as="nav"
      w="260px"
      flexShrink={0}
      px={5}
      py={6}
      display={{ base: "none", lg: "block" }}
      position="sticky"
      top={0}
      alignSelf="flex-start"
      height="100dvh"
    >
      <Flex align="center" gap={3} px={2} mb={8}>
        <Flex
          align="center"
          justify="center"
          w="36px"
          h="36px"
          rounded="control"
          bg="accent.solid"
          color="white"
        >
          <Plane size={18} />
        </Flex>
        <Box>
          <Text fontWeight="800" letterSpacing="-0.02em" lineHeight="1">
            FlyHub
          </Text>
          <Text textStyle="label" fontSize="10px">
            Inspeções
          </Text>
        </Box>
      </Flex>

      {SECTIONS.map((section, index) => (
        <Box key={section.title ?? index} mb={6}>
          {section.title && (
            <Text textStyle="label" px={3} mb={2}>
              {section.title}
            </Text>
          )}
          {section.items.map((item) => (
            <NavLink key={item.to} to={item.to} end={"end" in item ? item.end : false}>
              {({ isActive }) => (
                <Flex
                  align="center"
                  gap={3}
                  px={3}
                  py={2.5}
                  mb={1}
                  rounded="control"
                  bg={isActive ? "bg.surface" : "transparent"}
                  shadow={isActive ? "card" : "none"}
                  color={isActive ? "fg.default" : "fg.muted"}
                  fontWeight={isActive ? "700" : "500"}
                  fontSize="sm"
                  transition="background 140ms ease, color 140ms ease"
                  _hover={{ color: "fg.default" }}
                >
                  <Box color={isActive ? "accent.solid" : "fg.faint"} display="flex">
                    <item.icon size={18} />
                  </Box>
                  {item.label}
                </Flex>
              )}
            </NavLink>
          ))}
        </Box>
      ))}

      <Flex
        align="center"
        gap={2}
        px={3}
        py={2}
        mt="auto"
        position="absolute"
        bottom={6}
        left={5}
        right={5}
      >
        <StatusDot tone={eventsConnected ? "live" : "down"} size="8px" />
        <Text textStyle="readout" fontSize="11px" color="fg.faint">
          {eventsConnected ? "telemetria ativa" : "telemetria offline"}
        </Text>
      </Flex>
    </Box>
  );
}
