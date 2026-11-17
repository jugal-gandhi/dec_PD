----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date: 08/27/2025 07:26:17 PM
-- Design Name: 
-- Module Name: Decoder_32_2 - Behavioral
-- Project Name: 
-- Target Devices: 
-- Tool Versions: 
-- Description: 
-- 
-- Dependencies: 
-- 
-- Revision:
-- Revision 0.01 - File Created
-- Additional Comments:
-- 
----------------------------------------------------------------------------------



library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.all;

entity Decoder_32_2 is
generic (N: positive:= 32;
         es: positive:=2);
port( INPUT: in std_logic_vector(N-1 downto 0); 
      S: out std_logic;
      reg_O: Out std_logic_vector(5 downto 0);
      EXP_O: Out std_logic_vector(es-1 downto 0);
      inf: out std_logic;
--	  SF: out std_logic_vector(6 downto 0);
	  Mantissa : out std_logic_vector(N-es-3 downto 0));
end Decoder_32_2;


architecture Behavioral of Decoder_32_2 is

Component LS is
  Generic(N: Integer := 32);
  Port (Input: In std_logic_vector(29 downto 0);
        rc: In std_logic;
        k: Out std_logic_vector(4 downto 0);
        Output: Out std_logic_vector(29 downto 0));
end Component ;

signal Sign : STD_LOGIC;
signal R_Check : STD_LOGIC;
-----Signal for LOD--------------
signal k : STD_LOGIC_VECTOR(4 downto 0);  ------make length using log2
signal X : STD_LOGIC_VECTOR(N-3 downto 0);
signal reg : std_logic_vector(5 downto 0);
signal EXP: std_logic_vector(es-1 downto 0);
signal d5: std_logic_vector(N-3 downto 0);
signal d4: std_logic_vector(N-3 downto 0);
signal d_and_4: std_logic;
signal count4: std_logic;
signal d3: std_logic_vector(N-3 downto 0);
signal d_and_3: std_logic;
signal count3: std_logic;
signal d2: std_logic_vector(N-3 downto 0);
signal d_and_2: std_logic;
signal count2: std_logic;
signal d1: std_logic_vector(N-3 downto 0);
signal d_and_1: std_logic;
signal count1: std_logic;
signal d0: std_logic_vector(N-3 downto 0);
signal d_and_0: std_logic;
signal count0: std_logic;

signal tmp5 :  std_logic_vector(29 downto 0);
signal tmp4 :  std_logic_vector(29 downto 0);
signal tmp3 :  std_logic_vector(29 downto 0);
signal tmp2 :  std_logic_vector(29 downto 0);
signal tmp1 :  std_logic_vector(29 downto 0);
signal tmp0 :  std_logic_vector(29 downto 0);
signal zero_check: std_logic;

begin

----- For zero and inf checl---------
zero_check <= INPUT(N-1) when d_and_4=R_Check else '1';

process(zero_check, Sign)
begin
    if zero_check = '0' and Sign = '1' then
--    if not(zero_check) = Sign then
        inf <= '1';
    else
        inf <= '0';
    end if;
end process;

----Extracting Sign Bit
Sign <= INPUT(N-1);

----------Extracting First Regime bit to check for sequence for 0 or 1
R_Check <= INPUT(N-2);

--Left Shifting
--LS_M: LS port map (Input=>INPUT(N-3 downto 0), rc=>R_Check, k=>k, Output=>X);
d5 <= INPUT(N-3 downto 0);

  Detect_Proc: process(R_Check, d5, d4, d3, d2)
   begin
    if R_Check = '1' then 
    
       d_and_4 <= d5(29) and d5(28) and d5(27) and d5(26) and d5(25) and d5(24) and d5(23) and d5(22) and d5(21) and d5(20) and d5(19) and d5(18) and d5(17) and d5(16) and d5(15) and d5(14);
       d_and_3 <= d4(29) and d4(28) and d4(27) and d4(26) and d4(25) and d4(24) and d4(23) and d4(22) and d4(21);
       d_and_2 <= d3(29) and d3(28) and d3(27) and d3(26) and d3(25);
       d_and_1 <= d2(29) and d2(28) and d2(27);
       
    else
    
       d_and_4 <= d5(29) or d5(28) or d5(27) or d5(26) or d5(25) or d5(24) or d5(23) or d5(22) or d5(21) or d5(20) or d5(19) or d5(18) or d5(17) or d5(16) or d5(15) or d5(14);
       d_and_3 <= d4(29) or d4(28) or d4(27) or d4(26) or d4(25) or d4(24) or d4(23) or d4(22) or d4(21);
       d_and_2 <= d3(29) or d3(28) or d3(27) or d3(26) or d3(25);
       d_and_1 <= d2(29) or d2(28) or d2(27);
       
    end if;
 end process;
d_and_0 <= d1(29);

----Regime length count----
count4<= '1' when d_and_4=R_Check else '0';
count3<= '1' when d_and_3=R_Check else '0';
count2<= '1' when d_and_2=R_Check else '0';
count1<= '1' when d_and_1=R_Check else '0';
count0<= '1' when d_and_0=R_Check else '0';

----LEft Shifting----   
d4<= d5(29 downto 0) when count4='0' else d5(13 downto 0) & (15 downto 0 => '0');
d3<= d4(29 downto 0) when count3='0' else d4(21 downto 0) & (7 downto 0 => '0');
d2<= d3(29 downto 0) when count2='0' else d3(25 downto 0) & (3 downto 0 => '0');
d1<= d2(29 downto 0) when count1='0' else d2(27 downto 0) & (1 downto 0 => '0');
d0<= d1(29 downto 0) when count0='0' else d1(28 downto 0) & (0 downto 0 => '0');

----Regime length----   
k <= count4 & count3 & count2 & count1 & count0;

----Shifted Output----
X <= d0;



S <= Sign;

--reg <= "0" & k when R_Check /= Sign else "1" & NOT(k);
reg <= "1" & NOT(k) when R_Check = Sign else "0" & k;
Exp <= X(N-4 downto N-3-es);

reg_O <= reg;
EXP_O <= Exp;
--SF <= reg & (Exp xor (1 downto 0 => Sign));
--SF <= reg & Exp;
Mantissa <= zero_check & X(N-es-4 downto 0);

end Behavioral;
